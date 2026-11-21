"""TUI (Text User Interface) da Agentic Software Factory (ASF).

Esta é a interface principal do protótipo, implementada com Textual.
Oferece uma experiência interativa estilo "Claude Code":
- Sidebar com execuções
- Área principal com chat/log
- Input multi-linha na base
- Atualizações em tempo real

Comandos de teclado:
    - Enter: submeter texto
    - Ctrl+Q: sair
    - Ctrl+C: cancelar operação em curso
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListView,
    ListItem,
    Static,
)


# ---------------------------------------------------------------------------
# Estado persistido em JSON (partilhado entre sessões)
# ---------------------------------------------------------------------------
STATE_FILE = Path(__file__).resolve().parents[1] / ".asf_state.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"executions": {}, "audit": {}}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
class ExecutionList(ListView):
    """Lista de execuções na sidebar."""

    def __init__(self) -> None:
        super().__init__()
        self._items: dict[str, ListItem] = {}

    def add_execution(self, execution_id: str, issue: str) -> None:
        item = ListItem(Label(f"[b]{execution_id}[/b]\n{issue[:40]}..."))
        self._items[execution_id] = item
        self.append(item)

    def select_execution(self, execution_id: str) -> None:
        if execution_id in self._items:
            self.selected = self._items[execution_id]


class ChatLog(Static):
    """Área principal com o chat/log de execução."""

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._lines: list[str] = []

    def append(self, text: str, style: str = "") -> None:
        """Adiciona uma linha ao log."""
        line = f"[{style}]{text}[/{style}]" if style else text
        self._lines.append(line)
        self.update("\n".join(self._lines))

    def clear(self) -> None:
        self._lines.clear()
        self.update("")


# ---------------------------------------------------------------------------
# App principal
# ---------------------------------------------------------------------------
class ASFApp(App):
    """Aplicação TUI da Agentic Software Factory."""

    TITLE = "ASF — Agentic Software Factory"
    SUB_TITLE = "Protótipo v0.1.0"

    CSS = """
    Screen {
        background: $surface;
    }

    #sidebar {
        width: 32;
        height: 100%;
        border: solid $primary;
        padding: 1;
    }

    #main {
        height: 1fr;
        padding: 1;
    }

    #chat {
        height: 1fr;
        padding: 1;
        background: $panel;
    }

    #input-area {
        height: 3;
        padding: 0 1;
    }

    #chat-input {
        border: solid $primary;
    }

    #status-bar {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Sair", show=True),
        Binding("ctrl+c", "cancel", "Cancelar", show=True),
    ]

    current_execution_id: reactive[Optional[str]] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("[b]EXECUÇÕES[/b]")
                yield ExecutionList()
            with Vertical(id="main"):
                yield ChatLog(id="chat")
                yield Input(placeholder="Submeta uma Issue ou comando...", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        """Carrega estado anterior ao iniciar."""
        state = _load_state()
        chat: ChatLog = self.query_one("#chat", ChatLog)
        chat.append("Bem-vindo à [b]Agentic Software Factory[/b]!", "bold")
        chat.append("Submeta uma Issue ou User Story para iniciar.", "dim")
        chat.append("")
        chat.append("Exemplo: [cyan]Adicionar login OAuth2 ao sistema[/cyan]")
        chat.append("")

        if state["executions"]:
            exec_list: ExecutionList = self.query_one(ExecutionList)
            for exec_id, data in state["executions"].items():
                exec_list.add_execution(exec_id, data.get("issue", ""))

    @on(Input.Submitted, "#chat-input")
    def submit_issue(self, event: Input.Submitted) -> None:
        """Processa o texto submetido pelo utilizador."""
        text = event.value.strip()
        if not text:
            return

        event.input.value = ""
        chat: ChatLog = self.query_one("#chat", ChatLog)

        # Mostra o input do utilizador
        chat.append(f"[bold yellow]> {text}[/bold yellow]")
        chat.append("")

        # Cria nova execução
        state = _load_state()
        execution_id = f"exec-{len(state['executions']) + 1:04d}"
        state["executions"][execution_id] = {
            "execution_id": execution_id,
            "status": "received",
            "issue": text,
            "current_agent": "orchestrator",
            "failure_reason": None,
        }
        state["audit"].setdefault(execution_id, []).append(
            {"event": "issue_received", "execution_id": execution_id, "issue": text}
        )
        _save_state(state)
        self.current_execution_id = execution_id

        # Atualiza sidebar
        exec_list: ExecutionList = self.query_one(ExecutionList)
        exec_list.add_execution(execution_id, text)

        # Simula workflow
        self._simulate_workflow(execution_id, text)

    @work(thread=True)
    async def _simulate_workflow(self, execution_id: str, issue: str) -> None:
        """Simula o workflow ASF com os agentes especializados."""
        chat: ChatLog = self.query_one("#chat", ChatLog)

        agents = [
            ("Orchestrator", "A classificar a Issue e delegar...", "magenta"),
            ("Requirements", "A interpretar a Issue e derivar requisitos...", "blue"),
            ("Architecture", "A planear a execução e decompor em tarefas...", "cyan"),
            ("Developer", "A gerar o ChangeSet (patch)...", "green"),
            ("Testing", "A derivar e executar testes...", "yellow"),
            ("Security", "A auditar a segurança da alteração...", "red"),
            ("Review", "A revisar a alteração final...", "white"),
        ]

        for agent_name, message, color in agents:
            await asyncio.sleep(0.8)
            chat.append(f"[{color}][{agent_name}][/] {message}")

        await asyncio.sleep(0.5)
        chat.append("")
        chat.append("[bold green]✅ Execução concluída com sucesso![/bold green]")
        chat.append(f"[dim]execution_id: {execution_id}[/dim]")
        chat.append("")

        # Atualiza estado final
        state = _load_state()
        state["executions"][execution_id]["status"] = "done"
        state["executions"][execution_id]["current_agent"] = "completed"
        state["audit"][execution_id].append(
            {"event": "execution_completed", "execution_id": execution_id}
        )
        _save_state(state)

    def action_cancel(self) -> None:
        """Cancela a operação em curso."""
        chat: ChatLog = self.query_one("#chat", ChatLog)
        chat.append("[red]⚠ Operação cancelada pelo utilizador.[/red]")

    def action_quit(self) -> None:
        """Sai da aplicação."""
        self.exit()


def main() -> None:
    """Ponto de entrada da TUI ASF."""
    app = ASFApp()
    app.run()


if __name__ == "__main__":
    main()