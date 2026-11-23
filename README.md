# Agentic Software Factory (ASF) — Protótipo

Repositório de implementação da **Agentic Software Factory** (ASF), plataforma que
recebe trabalho de Engenharia de Software sob a forma de **Issues** ou
**User Stories** e coordena **agentes especializados** para analisar, planear,
propor e validar alterações a um projeto de software.

O protótipo é uma **TUI (Textual)** com sidebar de execuções, chat/log em tempo
real e input na base. Os agentes falam com o LLM real do `chat.iaedu.pt`
(um único modelo, `gpt-5.5`, para todos os agentes).

## Âmbito do protótipo

O protótipo demonstra cinco coisas, e mais nada:

1. Receção de uma Issue/User Story e passagem pelo fluxo de orquestração.
2. Responsabilidade agêntica real — cada passo do fluxo chama o LLM.
3. Utilização de Tools (reais sobre um repositório simulado, e determinísticas).
4. Um ponto de **Human Approval** (`y`/`n` no chat) antes de aplicar o patch.
5. **Audit/Logging** de todas as ações e resultados do fluxo.

Tudo o que não serve estes cinco pontos fica fora (ver
[O que ficou fora](#o-que-ficou-fora)).

## Estado atual

| Módulo | Estado |
|---|---|
| `asf/llm/client.py` | ✅ implementado — pedido multipart + stream NDJSON |
| `asf/tui.py` | ✅ implementado — chat com streaming, sidebar, estado por execução |
| `asf/core/state.py` | ⬜ a implementar — `ASFState` + persistência + `log()` |
| `asf/core/tools.py` | ⬜ a implementar — tools + matriz de permissões + `call_tool()` |
| `asf/agents/roles.py` | ⬜ a implementar — 7 papéis como dados |
| `asf/agents/flow.py` | ⬜ a implementar — `run_flow()` com os 7 passos e a aprovação |

Neste momento a TUI já envia a Issue ao LLM e faz streaming da resposta; o fluxo
de agentes liga-se a seguir através de `run_flow()`.

## Estrutura do projeto

```text
asf/
├── README.md
├── requirements.txt
├── .env.example              # ASF_LLM_API_KEY (única variável)
├── .env                      # chave real (gitignored)
├── .asf_state.json           # estado das execuções em runtime (gitignored)
├── .gitignore
├── mock_repo/                # repositório-alvo do protótipo (dados, não código)
│   ├── README.md
│   ├── app/service.py
│   └── tests/test_service.py
└── asf/                      # pacote Python
    ├── __init__.py
    ├── main.py               # entry point: arranca a TUI
    ├── tui.py                # aplicação Textual + adaptador de UI do fluxo
    ├── core/
    │   ├── __init__.py
    │   ├── state.py          # ASFState (dataclass), load/save, log(), brief()
    │   └── tools.py          # tools, AGENT_TOOLS, call_tool() com verificação
    ├── agents/
    │   ├── __init__.py
    │   ├── roles.py          # os 7 papéis do fluxo, como dados
    │   └── flow.py           # run_flow(state, client, ui)
    └── llm/
        ├── __init__.py
        └── client.py         # LLMClient (agent-chat da chat.iaedu.pt)
```

Não há um ficheiro por agente nem classes de agente: um agente é uma entrada em
`agents/roles.py`. Também não há `mocks/` de Python — o repositório-alvo é a
pasta `mock_repo/`, lida pelas tools.

## O que cada ficheiro faz

### `asf/main.py`

Entry point. Importa `asf.tui.main` e chama-a. Sem lógica.

### `asf/tui.py`

Toda a interface e a ponte entre o fluxo (que corre numa thread) e o ecrã.

- `ChatLog` — linhas de chat. `append(texto, style="")` escreve markup;
  `stream(delta)` acrescenta texto literal (escapado) à linha em curso. É o
  único widget que o fluxo toca.
- `ExecutionList` — sidebar; uma entrada por execução.
- `ASFApp` — compõe o layout, carrega o estado no arranque, trata do `Input` e
  corre `run_flow()` num worker `@work(thread=True)`, enviando cada fragmento
  para o ecrã com `call_from_thread`.
- **Adaptador de UI** (o que `flow.py` recebe):
  - `say(texto, style="")` → `ChatLog.append`
  - `stream(delta)` → `ChatLog.stream`
  - `approve(pergunta) -> bool` → escreve a pergunta no chat, guarda
    `self._approval_event`/`self._approval_answer` e **bloqueia** a thread até o
    utilizador responder (timeout de 60 s → `False`).
- **Aprovação `y`/`n`**: enquanto `self._awaiting_approval` estiver ativo, o
  handler do `Input` só interpreta `y`/`n`; qualquer outro texto é ignorado com
  aviso. Resolvido o `threading.Event`, o fluxo continua.
- Persistência: cria a execução, guarda `thread_id`, `status` e `audit` no
  `.asf_state.json` (via `ASFState.save`).

### `asf/llm/client.py` ✅

Cliente da API de **agent-chat** da chat.iaedu.pt. A API não é compatível com
OpenAI: pedido `multipart/form-data`, resposta em NDJSON. Tudo com a stdlib.

- Constantes: `ENDPOINT`, `CHANNEL_ID`, `MODEL = "gpt-5.5"`, `TIMEOUT`.
- `LLMClient`:
  - `stream(message, thread_id=None)` → iterador de eventos (`start`, `token`,
    `message`, `done`, `error`);
  - `chat(message, thread_id=None)` → resposta completa em texto;
  - `new_thread()` → novo `thread_id` (`sb-<hex>`);
  - `configured` → `False` se faltar `ASF_LLM_API_KEY`.
- Helpers privados: `_multipart()` (codifica os campos) e `_events()` (parse
  linha a linha do stream).

### `asf/core/state.py` ⬜

Estado partilhado, uma única dataclass, sem lógica de negócio.

```python
@dataclass
class ASFState:
    execution_id: str
    issue: str
    status: str                  # ver tabela de estados
    thread_id: str
    current_agent: str
    requirements: str = ""
    plan: dict = field(default_factory=dict)
    patch: str = ""
    test_results: dict = field(default_factory=dict)
    security_results: dict = field(default_factory=dict)
    review: str = ""
    approval: dict = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)
    failure_reason: str | None = None
```

- `load(path) -> ASFState` / `save(path)` — serializa com `dataclasses.asdict`;
  o `.asf_state.json` guarda `executions` (uma entrada `ASFState` por execução)
  e o `audit` de cada uma.
- `log(event, **campos)` — acrescenta `{"ts", "event", **campos}` ao `audit`.
  É o único mecanismo de logging: não há módulo `audit.py`.
- `brief() -> str` — resumo compacto (issue, rota, requisitos, patch, resultados)
  que vai nos prompts. Evita reenviar o estado inteiro ao LLM a cada passo.

Estados: `received → analysing → planning → developing → awaiting_approval →
testing → security → reviewing → done`, com saídas `rejected` e `failed`.

### `asf/core/tools.py` ⬜

As tools e a matriz de permissões, num só ficheiro.

- `TOOLS: dict[str, Callable]` — implementação de cada tool.
- `AGENT_TOOLS: dict[str, set[str]]` — a matriz (tabela abaixo).
- `call_tool(state, agent, name, **kwargs) -> str`:
  1. verifica `name in AGENT_TOOLS[agent]` (senão `PermissionError` e evento
     `tool_denied` no audit);
  2. executa a função;
  3. registra `tool_call` com agente, tool, argumentos, duração e ok/erro;
  4. devolve o resultado em texto, que entra no prompt do passo seguinte.

| Tool | Tipo | O que faz |
|---|---|---|
| `read_issue(state)` | real | devolve a Issue da execução |
| `read_docs(path)` | real | lê `mock_repo/README.md` e docs |
| `read_repo(path)` | real | árvore de ficheiros de `mock_repo/` |
| `grep(pattern, path)` | real | regex linha a linha nos ficheiros |
| `create_patch(state, instrucoes)` | determinística | gera um diff textual (não escreve no disco) |
| `run_tests(state)` | determinística | corre a checklist de testes sobre o patch |
| `static_analysis(state)` | determinística | procura padrões de risco (`eval`, `exec`, segredos, SQL concatenado) |

`read_repo`/`grep`/`read_docs` leem ficheiros a sério: é a "tool real" exigida.
`create_patch`/`run_tests`/`static_analysis` são simuladas e determinísticas, para
a demo não depender de escrever no disco nem de executar terminal.

### `asf/agents/roles.py` ⬜

Os 7 papéis do fluxo, por ordem, como dados — sem classes nem métodos:

```python
ROLES = [
    {"name": "Orchestrator", "tool": "read_issue",
     "prompt": "Classifica a Issue (bug/feature/refactor/security) e devolve um plano curto.",
     "event": "route_defined"},
    ...
]
```

O `flow.py` percorre esta lista; acrescentar um agente é acrescentar um dict.

### `asf/agents/flow.py` ⬜

O ciclo, numa função:

```python
def run_flow(state: ASFState, client: LLMClient, ui: UI) -> ASFState:
```

`UI` é um protocolo pequeno — `say(texto)`, `stream(delta)`, `approve(pergunta)`
— por isso o fluxo não importa Textual e pode ser corrido em teste.

Por cada papel de `ROLES`:

1. `state.current_agent = role["name"]`;
2. corre a tool do papel com `call_tool(...)` (se existir);
3. monta o prompt: instrução do papel + `state.brief()` + saída da tool;
4. `client.stream(prompt, state.thread_id)` e envia os tokens para `ui.stream`;
5. guarda a resposta no campo certo do estado (requisitos, plano, patch,
   resultados, review);
6. `state.log(role["event"], agent=..., summary=...)`;
7. no passo **Developer**, depois do patch: `ui.approve("Aplicar o patch? (y/n)")`
   → `approval_granted` ou `approval_rejected` (neste caso `status="rejected"` e
   o fluxo para).

Erros (`LLMError`, `PermissionError`) → `status="failed"`, `failure_reason`
preenchido, evento no audit e regresso da função. Sem retries.

## Fluxo de execução

Todos os passos usam o mesmo `LLMClient` e o mesmo `thread_id`: os agentes veem
o que os anteriores disseram.

| # | Agente | Tool verificada | Guarda em | Evento de audit |
|---|---|---|---|---|
| 1 | Orchestrator | `read_issue` | `plan["route"]`, `plan["steps"]` | `route_defined` |
| 2 | Requirements | `read_docs` | `requirements` | `requirements_ready` |
| 3 | Architecture | `read_repo`, `grep` | `plan["design"]` | `plan_ready` |
| 4 | Developer | `create_patch` | `patch` | `patch_proposed` |
| 4b | **Human Approval (y/n)** | — | `approval` | `approval_granted` / `approval_rejected` |
| 5 | Testing | `run_tests` | `test_results` | `tests_ok` / `tests_failed` |
| 6 | Security | `static_analysis` | `security_results` | `security_ok` / `security_findings` |
| 7 | Review | — | `review` | `execution_completed` / `execution_failed` |

Cada passo faz **uma chamada real** ao LLM (7 por execução, ~15-25 s).

## Matriz de permissões

Implementada em `core/tools.py` (`AGENT_TOOLS`), verificada em cada `call_tool`:

| Agente | Tools autorizadas |
|---|---|
| Orchestrator | `read_issue` |
| Requirements | `read_docs` |
| Architecture | `read_repo`, `grep` |
| Developer | `read_repo`, `create_patch` |
| Testing | `run_tests` |
| Security | `static_analysis` |
| Review | — |

Uma tool fora da matriz não é executada: gera `tool_denied` no audit e o fluxo
termina com `status="failed"`.

### O que ficou fora

O relatório descreve uma matriz maior (`write_audit`, `update_memory`,
`request_approval`, `exec_terminal`, `detect_injection`) e a cadeia de validação
de `exec_terminal` (allowlist, confirmação dupla). No protótipo:

- `write_audit` → é `state.log()`;
- `request_approval` → é o passo de aprovação `y`/`n` da TUI, não uma tool;
- `update_memory`/`trust_levels`/`retry_count` → nada os lê, não existem;
- `exec_terminal` → não há execução de comandos, logo não há allowlist nem
  confirmação dupla a demonstrar;
- `detect_injection` → coberto por `static_analysis`.

## LLM — chat.iaedu.pt

- **Endpoint:** `POST https://api.iaedu.pt/agent-chat//api/v1/agent/<agent_id>/stream`
- **Autenticação:** header `x-api-key` (chave no `.env`)
- **Pedido:** `multipart/form-data` com `channel_id`, `thread_id`, `user_info` e
  `message`
- **Resposta:** stream NDJSON com eventos `start`, `token`, `message`, `done`
- **Configuração:** só `ASF_LLM_API_KEY`
- **Sem chave:** o fluxo não arranca; a TUI mostra o erro no chat. Não há
  respostas simuladas.

```python
from asf.llm import LLMClient

client = LLMClient()
for event in client.stream("Olá"):
    if event["type"] == "token":
        print(event["content"], end="")
```

## Interface — Textual (TUI)

- **Sidebar**: lista de execuções (`ExecutionList`)
- **Área principal**: chat/log (`ChatLog`), com streaming token a token
- **Input** na base: Issues/User Stories e respostas de aprovação `y`/`n`
- **Teclas**: `Enter` submete, `Ctrl+Q` sai

Cores do log: `[Orchestrator]` magenta, requisitos azul, arquitetura ciano,
developer verde, testing amarelo, security vermelho, review branco.

## Ferramentas Python

| Finalidade | Ferramenta | Uso |
|---|---|---|
| Interface | `textual` | TUI, widgets, workers |
| HTTP + JSON | `http.client`, `json` (stdlib) | cliente do agent-chat e NDJSON |
| Estado | `dataclasses` (stdlib) | `ASFState` e serialização |
| Ficheiros | `pathlib`, `re` (stdlib) | tools reais sobre `mock_repo/` |
| Configuração | `python-dotenv` | carregar `ASF_LLM_API_KEY` |
| PDFs | `pypdf` | previsto para `read_docs` com Issues em PDF |

## Instalação e execução

```bash
git clone https://github.com/franciscocosta4/asf.git
cd asf

python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# editar .env e pôr a chave em ASF_LLM_API_KEY

python -m asf.main
```

> O `.env` é ignorado pelo Git — a chave nunca deve ser commitada. Use o
> `.env.example` como modelo.

### `requirements.txt`

```
textual
python-dotenv
pypdf
```

### `.env.example`

```ini
ASF_LLM_API_KEY=sua_chave_aqui
```

## Ligações

- **Repositório GitHub:** https://github.com/franciscocosta4/asf.git
- **Relatório do projeto:** `07.ESW_Etapa3_Comportamento_Prototipo_Avaliacao_v1_ECT.pdf`
- **Curso:** Engenharia de Informática, Universidade de Trás-os-Montes e Alto Douro

## Licença

MIT License.
