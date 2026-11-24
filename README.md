# Agentic Software Factory (ASF) — Protótipo

Repositório de implementação da **Agentic Software Factory** (ASF), plataforma que
recebe trabalho de Engenharia de Software sob a forma de **Issues** ou
**User Stories** e coordena **agentes especializados** para analisar, planear,
propor e validar alterações a um projeto de software.

O protótipo é uma **TUI (Textual)** com sidebar de execuções, chat/log em tempo
real e input na base. Os agentes falam com o LLM real do `chat.iaedu.pt`
(um único modelo, `gpt-5.5`, para todos os agentes).

## Âmbito do protótipo

O protótipo demonstra cinco coisas:

1. Receção de uma Issue/User Story e passagem pelo **fluxo de orquestração**
   com os 6 agentes.
2. Responsabilidade agêntica real — cada passo do fluxo chama o LLM.
3. Utilização de **Tools**, incluindo `exec_terminal` com allowlist e aprovação.
4. **Human Approval** (`y`/`n` no chat): aplicar o ChangeSet, executar comandos e
   gravar memória.
5. **Audit/Logging** de todas as ações e resultados, em `.json`.

Além disso, o fluxo tem **retry/replan** (até 3 tentativas, com escalonamento
para o utilizador) e **memória do projeto** em `memory.md` por repositório.

## Estado atual

| Módulo | Estado |
|---|---|
| `asf/llm/client.py` | ✅ implementado — pedido multipart + stream NDJSON |
| `asf/tui.py` | ✅ implementado — chat com streaming, sidebar, estado por execução |
| `asf/core/state.py` | ⬜ a implementar — `ASFState` + persistência + `log()` |
| `asf/core/tools.py` | ⬜ a implementar — tools + matriz + validação + `exec_terminal` |
| `asf/core/memory.py` | ⬜ a implementar — `memory.md` (leitura, confirmação, append) |
| `asf/agents/roles.py` | ⬜ a implementar — os 6 agentes como dados |
| `asf/agents/flow.py` | ⬜ a implementar — `run_flow()` com retry e aprovações |

Neste momento a TUI já envia a Issue ao LLM e faz streaming da resposta; o fluxo
de agentes liga-se a seguir através de `run_flow()`.

## Estrutura do projeto

```text
asf/
├── README.md
├── requirements.txt
├── .env.example              # ASF_LLM_API_KEY (única variável)
├── .env                      # chave real (gitignored)
├── .asf_state.json           # execuções + audit em runtime (gitignored)
├── .gitignore
├── mock_repo/                # repositório-alvo do protótipo (dados, não código)
│   ├── README.md
│   ├── memory.md             # memória do projeto (versionada, editável à mão)
│   ├── app/service.py
│   └── tests/test_service.py
└── asf/                      # pacote Python
    ├── __init__.py
    ├── main.py               # entry point: arranca a TUI
    ├── tui.py                # aplicação Textual + adaptador de UI do fluxo
    ├── core/
    │   ├── __init__.py
    │   ├── state.py          # ASFState (dataclass), load/save, log(), brief()
    │   ├── tools.py          # tools, AGENT_TOOLS, call_tool(), exec_terminal
    │   └── memory.py         # memory.md: load(), render(), add(), update()
    ├── agents/
    │   ├── __init__.py
    │   ├── roles.py          # os 6 agentes do fluxo, como dados
    │   └── flow.py           # run_flow(state, client, ui) + retry/replan
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
    change_set: str = ""
    command_log: list[dict] = field(default_factory=list)
    test_results: dict = field(default_factory=dict)
    security_results: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    approval: dict = field(default_factory=dict)
    retry_count: int = 0
    audit: list[dict] = field(default_factory=list)
    failure_reason: str | None = None
```

- `load(path) -> ASFState` / `save(path)` — serializa com `dataclasses.asdict`;
  o `.asf_state.json` guarda `executions` (uma entrada `ASFState` por execução)
  e o `audit` de cada uma.
- `log(event, **campos)` — acrescenta `{"ts", "event", **campos}` ao `audit`.
  É o único mecanismo de logging: `write_audit` da matriz resolve para `state.log()`.
- `brief() -> str` — resumo compacto (issue, rota, requisitos, ChangeSet,
  resultados) que vai nos prompts. Evita reenviar o estado inteiro ao LLM.
  Inclui a memória do projeto, limitada a ~5 entradas por categoria.

Estados: `received → analysing → planning → developing → testing → security →
reviewing → awaiting_approval → done`, com saídas `rejected`, `escalated` e
`failed`.

### `asf/core/tools.py` ⬜

As tools, a matriz de permissões e a validação de argumentos, num só ficheiro.

- `TOOLS: dict[str, Callable]` — implementação de cada tool.
- `AGENT_TOOLS: dict[str, set[str]]` — a matriz (tabela abaixo).
- `call_tool(state, agent, name, **kwargs) -> str`:
  1. valida o agente e os argumentos (tipo, caminho dentro do repo, padrão válido);
  2. verifica `name in AGENT_TOOLS[agent]` (senão `PermissionError`, evento
     `tool_denied` no audit, agente notificado);
  3. executa a função;
  4. registra `tool_call` com agente, tool, argumentos, duração e ok/erro;
  5. devolve o resultado em texto, que entra no prompt do passo seguinte.

`exec_terminal` não passa por este caminho: tem a cadeia própria da secção
[Execução de comandos](#execução-de-comandos-exec_terminal).

| Tool | Tipo | O que faz |
|---|---|---|
| `read_state(state)` | real | devolve `state.brief()` + memória do repo |
| `write_audit(state, evento)` | real | resolve para `state.log(...)` |
| `read_issue(state)` | real | devolve a Issue encapsulada como dado |
| `read_docs(root)` | real | lê `README.md`/`docs/` do repositório |
| `read_repo(root, path=None)` | real | árvore de ficheiros do repositório |
| `grep(pattern, root)` | real | regex linha a linha nos ficheiros |
| `create_patch(state, instrucoes)` | determinística | gera um diff textual (não escreve no disco) |
| `exec_terminal(state, comando)` | real | corre um comando da allowlist (ver secção própria) |
| `run_tests(state)` | real | `pytest -q` em `mock_repo/tests` quando existir; senão checklist |
| `static_analysis(state)` | determinística | padrões de risco (`eval`, `exec`, segredos, SQL concatenado) |
| `detect_injection(state)` | determinística | procura instruções embutidas em fontes untrusted |
| `update_memory(state, entradas)` | real (append) | propõe e grava entradas no `memory.md` após `y`/`n` |
| `request_approval(state, pergunta)` | UI | resolve para `ui.approve(...)` (não há segundo mecanismo) |

`read_repo`/`grep`/`read_docs`/`exec_terminal`/`run_tests` tocam no sistema a
sério; `create_patch`/`static_analysis`/`detect_injection` são determinísticas,
para a demo não depender do LLM para veredictos mecânicos.

### `asf/core/memory.py` ⬜

A memória durável de **um repositório**, num único `memory.md` na raiz desse
repositório (no protótipo, `mock_repo/memory.md`). Escopo por repo, não global.

- `load(root) -> dict[str, list[str]]` — parse das secções `## <categoria>`.
- `render(memory, limit=5) -> str` — texto para o prompt, no máximo 5 entradas
  por categoria (as mais recentes).
- `add(root, category, text)` — append de uma linha `- texto` na secção certa;
  cria o ficheiro a partir do template se não existir.
- `update(root, entries) -> list[str]` — valida categoria/formato, remove
  duplicados (case-insensitive) e devolve o que foi aceite.

**Confirmação obrigatória:** nenhuma entrada é gravada sem `ui.approve(...)`
(`y`/`n` no chat). Rejeitada → `memory_rejected` no audit e nada é escrito.
Aceite → `memory_updated`. Depois de gravada, só o utilizador a altera à mão
(append-only para o agente).

**Sem expiração por tempo**: a memória vive no repositório e é corrigida ou
apagada manualmente. Detalhes das categorias na secção
[Memória do projeto](#memória-do-projeto-memorymd).

### `asf/agents/roles.py` ⬜

Os 6 agentes do fluxo, por ordem, como dados — sem classes nem métodos:

```python
ROLES = [
    {"name": "Orchestrator", "tools": ["read_state", "write_audit", "update_memory", "request_approval"],
     "prompt": "Classifica a Issue, define a rota e a política de retry.",
     "event": "route_defined"},
    ...
]
```

O `flow.py` percorre esta lista; a re-invocação do *Requirements and review* no
fim é a mesma entrada executada outra vez com outro prompt (validação de
cobertura). Acrescentar um agente é acrescentar um dict.

### `asf/agents/flow.py` ⬜

O ciclo, numa função:

```python
def run_flow(state: ASFState, client: LLMClient, ui: UI) -> ASFState:
```

`UI` é um protocolo pequeno — `say(texto)`, `stream(delta)`, `approve(pergunta)`
— por isso o fluxo não importa Textual e pode ser corrido em teste.

Por cada passo:

1. `state.current_agent = role["name"]`;
2. corre as tools do papel com `call_tool(...)`;
3. monta o prompt: instrução do papel + `state.brief()` + saída das tools;
4. `client.stream(prompt, state.thread_id)` e envia os tokens para `ui.stream`;
5. guarda a resposta no campo certo do estado;
6. `state.log(role["event"], agent=..., summary=...)`;
7. aplica as aprovações e o retry/replan descritos abaixo.

## Agentes

| # | Agente | Função | Tools | Confiança |
|---|---|---|---|---|
| 1 | **Orchestrator** | Coordena, política de retry, audit logger, AI Memory | `read_state`, `write_audit`, `update_memory`, `request_approval` | Trusted |
| 2 | **Requirements and review** | Interpreta a Issue, deriva requisitos, deteta ambiguidades; **re-invocado no fim** para validar cobertura | `read_issue`, `read_docs` (untrusted encapsulado) | Read-only |
| 3 | **Architecture** | Analisa impacto, propõe plano | `read_repo`, `grep` | Read-only |
| 4 | **Developer** | Produz o ChangeSet | `read_repo`, `create_patch`, `exec_terminal` (com aprovação) | Write |
| 5 | **Testing** | Deriva e executa testes | `read_repo`, `run_tests` | Read + exec |
| 6 | **Security** | Audita segurança, deteta injeção | `read_repo`, `static_analysis`, `detect_injection` | Read-only |

Os trust levels (`Trusted`, `Read-only`, `Write`, `Read + exec`) estão definidos
mas **não são aplicados** nesta fase — ver [Futuro](#futuro).

## Fluxo de execução

Todos os passos usam o mesmo `LLMClient` e o mesmo `thread_id`: os agentes veem
o que os anteriores disseram.

| # | Agente | Tools | Guarda em | Evento de audit |
|---|---|---|---|---|
| 1 | Orchestrator | `read_state` | `plan["route"]`, retry policy | `route_defined` |
| 2 | Requirements | `read_issue`, `read_docs` | `requirements` | `requirements_ready` |
| 3 | Architecture | `read_repo`, `grep` | `plan["design"]` | `plan_ready` |
| 4 | Developer | `read_repo`, `create_patch`, `exec_terminal` | `change_set`, `command_log` | `patch_proposed`, `executed` |
| 4b | **Aprovação humana por comando** | — | `approval` | `approval_granted` / `approval_rejected` |
| 5 | Testing | `read_repo`, `run_tests` | `test_results` | `tests_ok` / `tests_failed` |
| 6 | Security | `read_repo`, `static_analysis`, `detect_injection` | `security_results` | `security_ok` / `security_findings` |
| 7 | Requirements (re-invocação) | `read_issue`, `read_docs` | `coverage` | `coverage_ok` / `coverage_gap` |
| 8 | **Aprovação humana final** | `request_approval` | `approval` | `approval_granted` / `approval_rejected` |

Cada passo faz **uma chamada real** ao LLM (~7 chamadas por execução, mais as
repetições do retry).

### Retry / replan

Máquina de estados do tratamento de falhas:

- **Timeout, erro de rede ou resposta inválida (JSON)** no passo → retry local
  do mesmo passo, com o erro anexado ao prompt (máx. 3 tentativas).
- **`tests_failed` ou `security_findings`** → volta ao Developer com o feedback
  no prompt; `retry_count += 1`. Máx. 3 voltas.
- **`coverage_gap`** → volta ao Developer com os requisitos em falta.
- **`retry_count == 3`** → `status = "escalated"`: a execução pára, o chat pede
  intervenção humana (`y` para tentar mais uma volta, `n` para abortar).
- **Falha de permissão/validação de tool** → não há retry: `tool_denied`,
  `status = "failed"` e o motivo no chat.

Cada decisão gera eventos no audit (`retry`, `replan`, `escalated`, `aborted`).

## Execução de comandos (`exec_terminal`)

Antes de qualquer comando, validar (protocolo 5.5 e 5.2):

1. **Agente** — só o **Developer** tem `exec_terminal`.
2. **Argumentos** — comando não vazio, sem encadeamento (`;`, `&&`, `|`),
   sem redirecionamentos nem caminhos fora do repositório.
3. **Allowlist** — só comandos pré-aprovados correm.
4. **Aprovação humana** — `y`/`n` no chat, uma vez por comando.
5. **Confirmação dupla** — operações destrutivas exigem segunda confirmação.
6. **Executar e registar** — `executed`/`failed` no audit com comando, resultado
   e código de saída.

| Nível | Exemplos | Aprovação |
|---|---|---|
| read-only | `git status`, `ls`, `cat`, `grep`, `pytest --collect-only` | Automática |
| exec | `pytest -q`, `python -m pytest`, `git diff` | Uma vez por comando |
| destrutivo | `rm -rf`, `git reset --hard`, `DROP TABLE` | Bloqueia + confirmação dupla |

Allowlist do protótipo (comandos correm em `mock_repo/`, com `timeout` de 30 s e
saída limitada): `ls`, `cat`, `grep`, `git status`, `git diff`, `pytest -q`,
`python -m pytest`. Tudo o resto é rejeitado com `tool_rejected` no audit.

## Permissões das tools

Implementada em `core/tools.py` (`AGENT_TOOLS`), verificada em cada `call_tool`:

| Agente | Tools autorizadas |
|---|---|
| Orchestrator | `read_state`, `write_audit`, `update_memory`, `request_approval` |
| Requirements and review | `read_issue`, `read_docs` |
| Architecture | `read_repo`, `grep` |
| Developer | `read_repo`, `create_patch`, `exec_terminal` |
| Testing | `read_repo`, `run_tests` |
| Security | `read_repo`, `static_analysis`, `detect_injection` |

Uma tool fora da matriz não é executada: gera `tool_denied` no audit e o fluxo
termina com `status="failed"`.

### Mapeamentos e fora do protótipo

| Nome no relatório | No protótipo |
|---|---|
| `write_audit` | `state.log()` |
| `request_approval` | `ui.approve(...)` (`y`/`n` no chat) |
| `read_state` | `state.brief()` + memória do repo |
| `update_memory` | `core/memory.py` sobre `memory.md`, com confirmação |
| `detect_injection` | regex em `core/tools.py` |

Fica só para o futuro: aplicação dos **trust levels** (ver
[Futuro](#futuro)). Tudo o resto da matriz do relatório está no protótipo.

## Fontes confiáveis e não confiáveis

| Fonte | Confiança | Tratamento |
|---|---|---|
| System prompts / políticas | Trusted | Instrução direta |
| Instruções do Orchestrator | Trusted | Controlo do fluxo |
| Código do repositório | SemiTrusted | Contexto de código, sanitizado (`detect_injection`) |
| Documentação interna (`README.md`, `docs/`) | SemiTrusted | Contexto funcional, sanitizado |
| Issue / User Story | Untrusted | Encapsulada como dado, nunca como instrução |
| Output de agentes/LLM | Untrusted | Encapsulado, validado pelo Orchestrator |

## Memória do projeto (`memory.md`)

O que o agente aprende sobre o projeto não vai para o `.asf_state.json`: vai para
um `memory.md` na raiz do projeto-alvo. É texto simples, versionado com o
código, editável à mão e visível num `git diff`. Escopo **por repositório**.

```markdown
# Memória do projeto

## repo_fact
- Este projeto usa PostgreSQL, não MySQL.

## failed_approach
- Já tentámos X, não funcionou porque Y.

## docs
- A API Z não existe nesta versão.

## generated_file
- O ficheiro W é gerado, não editar.

## convention
- Seguimos o padrão A para controllers.
```

| Categoria | Serve para | Exemplo |
|---|---|---|
| `repo_fact` | factos do repositório que o agente não deduz do código | "usa PostgreSQL, não MySQL" |
| `failed_approach` | tentativas que falharam, para não repetir | "já tentámos X, falhou por Y" |
| `docs` | limitações de APIs/bibliotecas nesta versão | "a API Z não existe nesta versão" |
| `generated_file` | ficheiros gerados que não se editam | "o ficheiro W é gerado" |
| `convention` | padrões internos da equipa | "controllers seguem o padrão A" |

Regras:

- Categorias fixas (`CATEGORIES` em `core/memory.py`); categoria desconhecida é
  rejeitada com `memory_rejected` no audit.
- Uma entrada = uma linha, sem `\n`; máximo ~5 entradas por categoria no prompt.
- Duplicados case-insensitive são ignorados.
- **Confirmação do utilizador (`y`/`n`) antes de gravar** qualquer entrada.
- Sem expiração por tempo; o utilizador corrige ou apaga à mão.
- Consulta e edição pelo utilizador são manuais no ficheiro; uma vista na TUI
  fica para o futuro. O agente lê a memória automaticamente no início do fluxo.
- Só conhecimento durável ali entra. Timestamps, `status`, `failure_reason` e
  audit ficam no `.asf_state.json` (estado técnico, descartável).

Quem escreve o quê:

| Passo | Ação sobre a memória |
|---|---|
| Orchestrator | `read_state` — a memória entra no prompt e no `brief()` |
| Requirements (re-invocação) | propõe 0-2 linhas `categoria: texto` |
| Orchestrator | `update_memory` — pede confirmação e faz append do que for aceite |
| Regras determinísticas | execução `failed` → `failed_approach` com o motivo; ChangeSet cria ficheiro → `generated_file` |

O protocolo exige **dois exemplos de sugestões de IA corrigidas, rejeitadas ou
alteradas**. O demo cobre isso com `approval_rejected`/`memory_rejected` e com a
edição manual de uma entrada no `memory.md`.

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

### Consulta de estado, logs e memória

Ainda não há vistas dedicadas na TUI — a consulta é feita nos ficheiros:

- **Estado e Audit Log**: `.asf_state.json`, uma entrada por execução com o
  respetivo `audit`; o chat mostra o resumo da execução em curso.
- **AI Memory**: `mock_repo/memory.md`, consultada e editada à mão pelo
  utilizador. O agente lê-a automaticamente no início do fluxo (`read_state`),
  mas o utilizador não tem ainda um ecrã para a ver ou editar.
- Ver logs e memória dentro da TUI fica como implementação futura (ver
  [Futuro](#futuro)).

## Ferramentas Python

| Finalidade | Ferramenta | Uso |
|---|---|---|
| Interface | `textual` | TUI, widgets, workers |
| HTTP + JSON | `http.client`, `json` (stdlib) | cliente do agent-chat e NDJSON |
| Estado | `dataclasses` (stdlib) | `ASFState` e serialização |
| Ficheiros | `pathlib`, `re` (stdlib) | tools reais sobre `mock_repo/` |
| Comandos | `subprocess` (stdlib) | `exec_terminal` com allowlist e timeout |
| Configuração | `python-dotenv` | carregar `ASF_LLM_API_KEY` |
| PDFs | `pypdf` | previsto para `read_docs` com Issues em PDF |

## Futuro

Fora do protótipo atual, definido para não se perder:

- **Consulta dos Audit Logs na TUI** — vista por execução (agente, tool,
  aprovação, resultado), equivalente ao RF-52 adaptado de CLI para TUI. Hoje os
  logs são lidos no `.asf_state.json`.
- **Vista da AI Memory na TUI** — leitura e edição do `memory.md` do
  repositório. Hoje o ficheiro é consultado e editado à mão.
- **Trust levels** por agente, mantidos pelo Orchestrator num campo
  `trust_levels` do `ASFState` (`Trusted`, `Read-only`, `Write`, `Read + exec`).
  Serviriam para decidir automaticamente o que exige aprovação e para ajustar a
  confiança entre execuções.

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

