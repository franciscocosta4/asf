"""Cliente HTTP para o agent-chat da chat.iaedu.pt.

O endpoint não é compatível com OpenAI: o pedido é ``multipart/form-data`` e a
resposta é um stream NDJSON (uma linha JSON por evento), apesar de vir com
``Content-Type: text/event-stream``::

    {"type": "start",   "content": "Processing"}
    {"type": "token",   "content": "ola"}
    {"type": "message", "content": {"type": "ai", "content": "ola", ...}}
    {"type": "done",    "content": "<run_id>", "messageId": "..."}

Utilização::

    client = LLMClient()
    for event in client.stream("Olá"):
        print(event["type"], event["content"])
"""

from __future__ import annotations

import http.client
import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from dotenv import load_dotenv

ENDPOINT = (
    "https://api.iaedu.pt/agent-chat//api/v1/agent/"
    "cmor5objoex9gfp01vm7p95jh/stream"
)
CHANNEL_ID = "cmwt77abd0s80it01gdxa8n6w"

#: Modelo fixo no servidor — todos os agentes usam este mesmo modelo.
MODEL = "gpt-5.5"
TIMEOUT = 180.0
TERMINAL_EVENTS = frozenset({"done", "error"})

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class LLMError(RuntimeError):
    """Falha na comunicação com o LLM."""


class LLMClient:
    """Uma conversa (thread) com o agente do iaedu."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key if api_key is not None else os.getenv("ASF_LLM_API_KEY", "")
        self.api_key = key.strip()
        self.thread_id = self.new_thread()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def new_thread(self) -> str:
        """Inicia uma conversa nova e devolve o respetivo ``thread_id``."""
        self.thread_id = f"sb-{uuid.uuid4().hex[:16]}"
        return self.thread_id

    def stream(
        self, message: str, thread_id: str | None = None
    ) -> Iterator[dict[str, Any]]:
        """Envia ``message`` e itera os eventos até ``done``/``error``."""
        if not self.configured:
            raise LLMError("Defina ASF_LLM_API_KEY no .env")
        if not message.strip():
            raise ValueError("message não pode estar vazio")

        body, content_type = _multipart(
            {
                "channel_id": CHANNEL_ID,
                "thread_id": thread_id or self.thread_id,
                "user_info": "{}",
                "message": message,
            }
        )

        parts = urlsplit(ENDPOINT)
        connection_cls = (
            http.client.HTTPSConnection
            if parts.scheme == "https"
            else http.client.HTTPConnection
        )
        conn = connection_cls(parts.hostname, parts.port, timeout=TIMEOUT)
        try:
            conn.request(
                "POST",
                parts.path,
                body=body,
                headers={
                    "Content-Type": content_type,
                    "Accept": "text/event-stream",
                    "x-api-key": self.api_key,
                    "Content-Length": str(len(body)),
                },
            )
            response = conn.getresponse()
            if response.status >= 400:
                detail = response.read().decode("utf-8", "replace")[:300]
                raise LLMError(f"HTTP {response.status}: {detail}")

            for event in _events(response):
                yield event
                if event.get("type") in TERMINAL_EVENTS:
                    return
        except OSError as exc:
            raise LLMError(f"Falha de rede a contactar {ENDPOINT}: {exc}") from exc
        finally:
            conn.close()

    def chat(self, message: str, thread_id: str | None = None) -> str:
        """Devolve a resposta completa em texto (sem streaming)."""
        tokens: list[str] = []
        final: list[str] = []
        for event in self.stream(message, thread_id):
            kind, content = event.get("type"), event.get("content")
            if kind == "token" and content:
                tokens.append(content)
            elif kind == "message" and isinstance(content, dict):
                final.append(content.get("content") or "")
            elif kind == "error":
                raise LLMError(str(content))
        return "".join(tokens) or "".join(final)


def _multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    """Codifica ``fields`` como ``multipart/form-data``."""
    boundary = uuid.uuid4().hex
    body = "".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        f"\r\n\r\n{value}\r\n"
        for name, value in fields.items()
    )
    body += f"--{boundary}--\r\n"
    return body.encode("utf-8"), f"multipart/form-data; boundary={boundary}"


def _events(response: http.client.HTTPResponse) -> Iterator[dict[str, Any]]:
    """Converte as linhas NDJSON da resposta em eventos."""
    for raw_line in response:
        line = raw_line.decode("utf-8", "replace").strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line.startswith("{"):
            continue  # keep-alive, comentário SSE ou linha vazia
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event
