# Agentic Software Factory (ASF) — Protótipo

Repositório de implementação do protótipo da **Agentic Software Factory** (ASF), plataforma que recebe trabalho de Engenharia de Software sob a forma de **Issues** ou **User Stories** e coordena **agentes especializados** para analisar, planear, propor e validar alterações a um projeto de software.

O objetivo do protótipo é demonstrar uma **vertical slice** (seção 7.1 do relatório) de ponta a ponta: desde a submissão de uma Issue até à aprovação humana e registo de auditoria, com componentes simulados (Git repo e LLM podem ser mockados para demonstração sem credenciais).

---

## 📋 Estado atual

Apenas a estrutura de pastas base existe:

```
asf/
├── core/            ← criada (vazia, será populada em seguida)
├── agents/
├── tools/
├── llm/
├── cli/
├── orchestrator/
├── config/
├── README.md
├── requirements.txt
└── .env.example
```

> **Nota:** A pasta `core/` está vazia nesta versão inicial. Os ficheiros serão adicionados progressivamente.

---

## 🏗️ Futura estrutura do projeto (completa)

```text
asf/
├── asf/
│   ├── __init__.py
│   ├── main.py                # Ponto de entrada do pacote
│   ├── cli.py                 # Interface principal: Typer (submeter, status, approve)
│   ├── orchestrator.py        # Orquestrador central (coordena o fluxo entre agentes)
│   ├── config.py              # Configurações globais (allowlists, paths, LLM endpoint)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py          # Modelos de dados: Issue, ChangeSet, AuditEntry, ToolRequest
│   │   ├── state.py           # ASFState (dataclass partilhada entre agentes)
│   │   ├── permissions.py     # Matriz de permissões por agente
│   │   ├── tool_validator.py  # Validação de pedidos de ferramenta antes da execução
│   │   ├── approval.py        # Fluxo de aprovação humana
│   │   ├── audit.py           # Audit Log (registos imutáveis)
│   │   └── memory.py          # AI Memory (memória contextual persistente)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py            # Classe base Agent (interface comum)
│   │   ├── orchestrator_agent.py
│   │   ├── requirements_agent.py
│   │   ├── architecture_agent.py
│   │   ├── developer_agent.py
│   │   ├── testing_agent.py
│   │   └── security_agent.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py            # Tool base class + ToolRegistry
│   │   ├── read_tools.py      # read_state, read_issue, read_docs, read_repo, grep
│   │   ├── write_tools.py     # write_audit, update_memory, create_patch, exec_terminal
│   │   └── analysis_tools.py  # run_tests, static_analysis, detect_injection
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py          # LLMClient (chat.iaedu.pt — GPT-5.5 via OpenAI SDK)
│   └── mocks/
│       ├── __init__.py
│       ├── git_repo.py        # Repositório Git simulado (sistema de ficheiros)
│       └── llm.py             # Respostas fixas do LLM para demonstração sem API
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 🎯 Requisitos (do relatório)

### Requisitos Funcionais (RF)

| ID | Requisito | Descrição |
|----|-----------|-----------|
| US1 | Submeter Issue | Utilizador submete uma Issue/User Story à ASF |
| US2 | Acompanhar Estado | Consultar o estado atual de uma execução |
| US3 | Rastrear Pedido | Seguir o Issue original até ao resultado final |
| US4 | Interpretar Issue e Derivar Requisitos | O agente Requirements extrai requisitos funcionais e não funcionais |
| US5 | Decompor Objetivo em Tarefas | O agente Architecture/Planner cria o plano operacional |
| US6 | Identificar Riscos e Decisões Críticas | O agente Security identifica riscos de segurança |
| US7 | Replanear em Caso de Falha | O Orchestrator reage a erros e replaneia se necessário |
| US8 | Analisar Impacto no Repositório | Avaliar quais ficheiros serão alterados |
| US9 | Produzir ChangeSet | O agente Developer gera a proposta de alteração |
| US10 | Validar Argumentos Antes de Executar | O Orchestrator valida pedidos de ferramenta |
| US11 | Aplicar Menor Privilégio | Cada agente só acede às ferramentas da sua matriz |
| US12 | Derivar e Executar Testes | O agente Testing cria e executa testes |
| US13 | Auditar Segurança da Alteração | O agente Security analisa a proposta para vulnerabilidades |
| US14 | Revisar Alteração Final | O agente Requirements faz revisão final |
| US15 | Definir Condições de Conclusão | Critérios de aceite para encerrar a execução |
| US16 | Classificar Fontes de Dados | Separar conteúdo trusted vs untrusted |
| US17 | Detetar e Tratar Prompt Injection | Segurança contra injeção de instruções |
| US18 | Aprovar ou Rejeitar Ações de Risco | Aprovação humana para escrita/execução |
| US19 | Proteger Informação Sensível | Sem credenciais no código ou logs |
| US20 | Registar Execuções para Auditoria | Audit Log imutável |
| US21 | Reconstruir Sequência Operacional | Via Audit Log + AI Memory |
| US22 | Registar Aprovações | Quem aprovou, quando e porquê |
| US23 | Memorizar Factos do Projeto | AI Memory persiste contexto entre execuções |
| US24 | Confirmar Gravação na Memória | Verificar que a memória foi persistida |

### Requisitos Não Funcionais (RNF)

- **Segurança:** Princípio do menor privilégio; escrita no repositório exige aprovação humana
- **Auditoria:** Todas as decisões e ações registadas no Audit Log
- **Rastreabilidade:** Cada alteração pode ser traçada ao Issue original
- **Observabilidade:** Estado visível via CLI
- **Extensibilidade:** Novos agentes e ferramentas podem ser adicionados sem reescrever o Orchestrator
- **Simplicidade:** Arquitetura direta, sem dependências desnecessárias

---

## 🔐 Matriz de Permissões

Respeita estritamente a matriz do relatório. Cada agente tem ferramentas autorizadas específicas:

| Agente | Ferramentas Autorizadas |
|--------|------------------------|
| Orchestrator | `read_state`, `write_audit`, `update_memory`, `request_approval` |
| Requirements | `read_issue`, `read_docs` |
| Architecture | `read_repo`, `grep` |
| Developer | `read_repo`, `create_patch`, `exec_terminal` (com aprovação) |
| Testing | `read_repo`, `run_tests` |
| Security | `read_repo`, `static_analysis`, `detect_injection` |

> **Condição essencial:** Os agentes **não** podem modificar livremente todos os campos do `ASFState`. Apenas o Orchestrator escreve no estado global; cada agente apenas lê os campos necessários e propõe alterações através do Orchestrator.

---

## 🛡️ Validação de Ferramentas (Orchestrator)

O Orchestrator valida **todos** os pedidos de ferramenta antes de executar. Não basta verificar permissões no início do workflow.

### Cadeia de validação de `exec_terminal`

1. **Validar o agente** — Confirma que o agente solicitante tem permissão para `exec_terminal` (apenas Developer)
2. **Validar os argumentos** — Verifica se os argumentos são válidos e seguros
3. **Verificar allowlist de comandos** — Apenas comandos pré-aprovados são executados
4. **Solicitar aprovação humana** — Pausa a execução e pede confirmação ao utilizador
5. **Confirmação dupla** — Para operações destrutivas, exige confirmação adicional
6. **Executar e registar** — Executa o comando e regista o resultado no Audit Log

---

## 🧠 Troca entre Agentes

O modelo de troca baseia-se em **estado partilhado controlado**:

```
ASFState (dataclass)
  ├─ issue (Issue original)
  ├─ status (received → analysed → planned → developed → tested → reviewed → approved → done)
  ├─ current_agent (quem está responsável agora)
  ├─ requirements []
  ├─ execution_plan {}
  ├─ change_set
  ├─ test_results {}
  ├─ security_results {}
  ├─ review_results {}
  ├─ trust_levels {}
  ├─ approval_requests []
  ├─ retry_count
  ├─ audit_log []
  ├─ memory {}
  ├─ repository_id
  └─ failure_reason
```

**Fluxo:**
1. O **Orchestrator** recebe o `state` e classifica a entrada
2. Delega ao agente especializado correspondente, passando o `state`
3. O agente **lê apenas os campos permitidos** pela sua matriz
4. O agente **propõe alterações** ao estado (não modifica diretamente)
5. O **Orchestrator** valida as propostas, aplica as autorizadas e atualiza o `state`
6. O ciclo repete até a conclusão ou falha

> Alternativa futura: migração para LangGraph (grafo de estado) se a complexidade aumentar.

---

## 🛠️ Ferramentas Python

| Finalidade | Ferramenta | Uso |
|------------|-----------|-----|
| **Interface** | `typer` | CLI moderna com type hints, auto-ajuda e validação |
| **Leitura de ficheiros** | `pypdf` | Extrair texto de PDFs (Issues, documentação) |
| **Leitura de ficheiros** | `pathlib` | Manipulação de caminhos e leitura de ficheiros |
| **Serialização** | `dataclasses-json` | Serializar/deserializar `Issue`, `ChangeSet`, `AuditEntry`, `ASFState` |
| **LLM** | `openai` | Cliente para API do `chat.iaedu.pt` (GPT-5.5) |
| **Configuração** | `python-dotenv` | Carregar credenciais do `.env` |
| **YAML config** | `PyYAML` | Ficheiros de configuração |

---

## 🤖 LLM — chat.iaedu.pt

O protótipo utiliza a API do **chat.iaedu.pt** com o modelo **GPT-5.5** (via OpenAI SDK, compatível com endpoint customizado).

- **Endpoint:** `https://chat.iaedu.pt` (configurável via `.env`)
- **Autenticação:** Chave de API no ficheiro `.env`
- **Fallback:** Implementação de `llm/mock/llm.py` com respostas fixas para demonstração sem credenciais

---

## 🖥️ Interface — Typer

A interface principal é uma **CLI Typer** com os seguintes comandos planeados:

```bash
# Submeter uma Issue (texto ou ficheiro)
python -m asf.cli submit --issue "Adicionar login OAuth2"
python -m asf.cli submit --file issues/issue_001.json

# Consultar estado de uma execução
python -m asf.cli status --execution-id <id>

# Aprovar ou rejeitar uma ação
python -m asf.cli approve --execution-id <id> --decision approve
python -m asf.cli approve --execution-id <id> --decision reject

# Ver audit log
python -m asf.cli audit --execution-id <id>
```

---

## 📦 Instalação e Execução

```bash
# Clonar o repositório
git clone https://github.com/franciscocosta4/asf.git
cd asf

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com a chave da API chat.iaedu.pt (opcional para protótipo com mock)

# Executar
python -m asf.cli submit --issue "Exemplo de Issue"
```

### `requirements.txt` (planeado)

```text
typer
openai
dataclasses-json
pypdf
python-dotenv
PyYAML
```

### `.env.example` (planeado)

```ini
ASF_LLM_API_KEY=sua_chave_aqui
ASF_LLM_BASE_URL=https://chat.iaedu.pt
ASF_LLM_MODEL=gpt-5.5
ASF_REPO_PATH=./mock_repo
ASF_AUDIT_LOG_PATH=./audit_log.json
ASF_MEMORY_PATH=./ai_memory.json
```

---

## 🧭 Próximos Passos (ordem de implementação)

1. **`core/`** — Modelos (`models.py`), Estado (`state.py`), Permissões (`permissions.py`), Validador de ferramentas (`tool_validator.py`), Aprovação (`approval.py`), Auditoria (`audit.py`), Memória (`memory.py`)
2. **`tools/`** — Base + Registry, Read tools, Write tools, Analysis tools
3. **`llm/`** — Cliente para chat.iaedu.pt + mock
4. **`agents/`** — Classe base + 5 agentes especializados + orquestrador
5. **`orchestrator.py`** — Orquestração do fluxo entre agentes
6. **`cli.py`** — CLI Typer com comandos `submit`, `status`, `approve`, `audit`
7. **`config.py`** — Configurações globais
8. **Documentação** — Explicação de cada componente e decisões de arquitetura

---

## 🔗 Ligações

- **Repositório GitHub:** https://github.com/franciscocosta4/asf.git
- **Relatório do projeto:** `trabalho-eng.software (1).pdf` (Secção 7 — Protótipo)
- **Curso:** Engenharia de Informática, Universidade de Trás-os-Montes e Alto Douro

---

## 📄 Licença

MIT License — veja o ficheiro `LICENSE` (se aplicável).