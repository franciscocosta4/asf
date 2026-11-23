"""TUI (Textual) da Agentic Software Factory (ASF).

Chat com o LLM do chat.iaedu.pt: cada Issue submetida cria uma execução na
sidebar, abre um ``thread_id`` novo e faz streaming da resposta para o chat.

Teclas: Enter submete, Ctrl+Q sai.
"""

import json
import uuid
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from asf.llm import LLMClient, LLMError

STATE_FILE = Path(__file__).resolve().parents[1] / ".asf_state.json"


def _load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"executions": {}, "audit": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


class ChatLog(Static):
    """Chat/log: linhas com markup e uma linha em streaming."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._lines: list[str] = []
        self._streaming = False

    def append(self, text: str = "", style: str = "") -> None:
        self._lines.append(f"[{style}]{text}[/{style}]" if style else text)
        self._streaming = False
        self.update("\n".join(self._lines))

    def stream(self, delta: str) -> None:
        """Acrescenta texto literal (escapado) à linha em streaming."""
        if not self._streaming:
            self._lines.append("")
            self._streaming = True
        self._lines[-1] += escape(delta)
        self.update("\n".join(self._lines))


class ExecutionList(ListView):
    """Lista de execuções na sidebar."""

    def add_execution(self, execution_id: str, issue: str) -> None:
        self.append(ListItem(Label(f"[b]{execution_id}[/b]\n{escape(issue[:40])}")))


class ASFApp(App):
    """Aplicação TUI da Agentic Software Factory."""

    TITLE = "ASF — Agentic Software Factory"
    SUB_TITLE = "Protótipo v0.1.0"

    CSS = """
    Screen { background: $surface; }
    #sidebar { width: 32; height: 100%; border: solid $primary; padding: 1; }
    #main { height: 1fr; padding: 1; }
    #chat { height: 1fr; padding: 1; background: $panel; }
    #chat-input { height: 3; margin-top: 1; border: solid $primary; }
    """

    BINDINGS = [Binding("ctrl+q", "quit", "Sair")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("[b]EXECUÇÕES[/b]")
                yield ExecutionList()
            with Vertical(id="main"):
                yield ChatLog(id="chat")
                yield Input(placeholder="Submeta uma Issue ou User Story...", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        chat = self.query_one("#chat", ChatLog)
        chat.append("[bold]Bem-vindo à Agentic Software Factory![/bold]")
        chat.append("[dim]Submeta uma Issue ou User Story para falar com o LLM.[/dim]")
        chat.append()

        state = _load_state()
        exec_list = self.query_one(ExecutionList)
        for execution_id, data in state["executions"].items():
            exec_list.add_execution(execution_id, data.get("issue", ""))

        self.query_one("#chat-input", Input).focus()

    @on(Input.Submitted, "#chat-input")
    def submit_issue(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return

        chat = self.query_one("#chat", ChatLog)
        chat.append(f"[bold yellow]> {escape(text)}[/bold yellow]")
        chat.append()

        client = LLMClient()
        if not client.configured:
            chat.append("[bold red]❌ ASF_LLM_API_KEY não definida no .env[/bold red]")
            return

        state = _load_state()
        execution_id = f"exec-{len(state['executions']) + 1:04d}"
        thread_id = client.new_thread()
        state["executions"][execution_id] = {
            "execution_id": execution_id,
            "status": "running",
            "issue": text,
            "thread_id": thread_id,
            "current_agent": "orchestrator",
            "failure_reason": None,
        }
        state["audit"].setdefault(execution_id, []).append(
            {"event": "issue_received", "execution_id": execution_id, "issue": text}
        )
        _save_state(state)

        self.query_one(ExecutionList).add_execution(execution_id, text)
        self._run_llm(execution_id, text, thread_id, client, chat)

    @work(thread=True)
    def _run_llm(
        self,
        execution_id: str,
        issue: str,
        thread_id: str,
        client: LLMClient,
        chat: ChatLog,
    ) -> None:
        """Envia a Issue ao LLM e faz streaming da resposta para o chat."""

        def say(text: str = "", style: str = "") -> None:
            self.call_from_thread(chat.append, text, style)

        say("[magenta][Orchestrator][/] A enviar a Issue ao LLM...")
        say(f"[dim]thread_id: {thread_id}[/dim]")
        say()

        received = 0
        failure: str | None = None
        try:
            for event in client.stream(issue, thread_id=thread_id):
                kind, content = event.get("type"), event.get("content")
                if kind == "token" and content:
                    self.call_from_thread(chat.stream, content)
                    received += 1
                elif kind == "message" and received == 0 and isinstance(content, dict):
                    text = content.get("content") or ""
                    if text:
                        self.call_from_thread(chat.stream, text)
                        received += 1
                elif kind == "error":
                    failure = str(content)
                    break
        except LLMError as exc:
            failure = str(exc)
        except Exception as exc:  # noqa: BLE001 - a TUI não pode rebentar
            failure = f"{type(exc).__name__}: {exc}"

        say()
        if failure:
            say(f"[bold red]❌ {escape(failure)}[/bold red]")
        elif received == 0:
            failure = "resposta vazia do LLM"
            say("[bold red]❌ O LLM não devolveu texto.[/bold red]")
        else:
            say("[bold green]✅ Resposta recebida.[/bold green]")
        say(f"[dim]execution_id: {execution_id}[/dim]")
        say()

        self._finish(execution_id, failure)

    def _finish(self, execution_id: str, failure: str | None) -> None:
        """Grava o resultado da execução no estado e no audit."""
        state = _load_state()
        entry = state["executions"][execution_id]
        entry["status"] = "failed" if failure else "done"
        entry["current_agent"] = "orchestrator" if failure else "completed"
        entry["failure_reason"] = failure
        state["audit"].setdefault(execution_id, []).append(
            {
                "event": "execution_failed" if failure else "execution_completed",
                "execution_id": execution_id,
                **({"reason": failure} if failure else {}),
            }
        )
        _save_state(state)


def main() -> None:
    ASFApp().run()


if __name__ == "__main__":
    main()
