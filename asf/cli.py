"""Interface de linha de comando (CLI) da Agentic Software Factory (ASF).

Comandos principais:
    - submit   : submeter uma Issue / User Story
    - status   : consultar o estado de uma execução
    - approve  : aprovar ou rejeitar uma ação pendente
    - audit    : consultar o registo de auditoria de uma execução
"""

import json
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    help="Plataforma que coordena agentes especializados para transformar Issues em alterações validadas.",
)

# ---------------------------------------------------------------------------
# Persistência simples em JSON (protótipo)
# ---------------------------------------------------------------------------
STATE_FILE = Path(__file__).resolve().parents[1] / ".asf_state.json"


def _load() -> dict:
    """Carrega o estado persistido ou cria um estado vazio."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"executions": {}, "audit": {}}


def _save(state: dict) -> None:
    """Guarda o estado em JSON."""
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
@app.command()
def submit(
    issue: Optional[str] = typer.Option(
        None,
        help="Descrição da Issue ou User Story (texto livre).",
    ),
    file: Optional[str] = typer.Option(
        None,
        "--file",
        help="Caminho para ficheiro (JSON/YAML/PDF) com a Issue.",
    ),
) -> None:
    """Submeter uma nova Issue ao ASF."""
    if not issue and not file:
        raise typer.BadParameter(
            "Deve fornecer a descrição da Issue (--issue) ou um ficheiro (--file)."
        )

    state = _load()
    execution_id = f"exec-{len(state['executions']) + 1:04d}"

    state["executions"][execution_id] = {
        "execution_id": execution_id,
        "status": "received",
        "issue": issue or f"(issue lida do ficheiro: {file})",
        "current_agent": "orchestrator",
        "failure_reason": None,
    }
    state["audit"].setdefault(execution_id, []).append(
        {
            "event": "issue_received",
            "execution_id": execution_id,
            "issue": issue or f"(issue do ficheiro {file})",
        }
    )
    _save(state)
    typer.echo(f"[ASF] Issue submetida. execution_id={execution_id}")


@app.command()
def status(
    execution_id: str = typer.Option(..., help="ID da execução."),
) -> None:
    """Consultar o estado de uma execução."""
    state = _load()
    execution = state["executions"].get(execution_id)
    if execution is None:
        typer.echo(f"[ASF] Execução não encontrada: {execution_id}")
        raise typer.Exit(code=1)
    typer.echo(json.dumps(execution, indent=2, ensure_ascii=False, default=str))


@app.command()
def approve(
    execution_id: str = typer.Option(..., help="ID da execução."),
    decision: str = typer.Option(..., help="Decisão: 'approve' ou 'reject'."),
) -> None:
    """Aprovar ou rejeitar uma ação pendente de uma execução."""
    state = _load()
    execution = state["executions"].get(execution_id)
    if execution is None:
        typer.echo(f"[ASF] Execução não encontrada: {execution_id}")
        raise typer.Exit(code=1)
    if decision not in ("approve", "reject"):
        raise typer.BadParameter("A decisão deve ser 'approve' ou 'reject'.")

    execution["status"] = "approved" if decision == "approve" else "rejected"
    execution["approval_decision"] = decision
    state["audit"].setdefault(execution_id, []).append(
        {"event": "human_approval", "execution_id": execution_id, "decision": decision}
    )
    _save(state)
    typer.echo(f"[ASF] Decisão '{decision}' registada na execução {execution_id}.")


@app.command()
def audit(
    execution_id: str = typer.Option(..., help="ID da execução."),
) -> None:
    """Consultar o registo de auditoria de uma execução."""
    state = _load()
    entries = state["audit"].get(execution_id, [])
    typer.echo(
        json.dumps(
            {"execution_id": execution_id, "audit": entries},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Executa o CLI da ASF."""
    app()


if __name__ == "__main__":
    app()