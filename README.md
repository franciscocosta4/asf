# Agentic Software Factory (ASF) — Protótipo

Repositório de implementação da **Agentic Software Factory** (ASF), plataforma que recebe trabalho de Engenharia de Software sob a forma de **Issues** ou **User Stories** e coordena **agentes especializados** para analisar, planear, propor e validar alterações a um projeto de software.

O protótipo está totalmente **TUI (Textual)** — uma interface interativa estilo "Claude Code", com:
- Sidebar com lista de execuções
- Área principal com chat/log em tempo real
- Input integrado na base da janela
- Atualizações assíncronas e reativas

## Estado atual

Apenas a estrutura de pastas base existe:

```
asf/
├── core/            ← criada (vazia, será populada em seguida)
├── agents/
├── tools/
├── llm/
├── tui/             ← TUI interativa (substitui CLI)
├── main.py          ← entry point para TUI
├── tui.py           ← aplicação Textual principal
├── README.md        ← atualizado com TUI
├── requirements.txt   ← atualizado com Textual
├── .env.example
├── .gitignore
└── README.md
```

## Futura estrutura do projeto (completa)

```text
asf/
├── asf/
│   ├── __init__.py
│   ├── main.py                # Ponto de entrada (TUI)
│   ├── tui.py                 # Aplicação TUI principal (Textual)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py          # Modelos de dados
│   │   ├── state.py           # ASFState (dataclass partilhada)
│   │   ├── permissions.py     # Matriz de permissões
│   │   ├── tool_validator.py  # Validação de ferramentas
│   │   ├── approval.py        # Aprovação humana
│   │   ├── audit.py           # Audit Log
│   │   └── memory.py          # AI Memory
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py            # Classe base Agent
│   │   ├── orchestrator_agent.py
│   │   ├── requirements_agent.py
│   │   ├── architecture_agent.py
│   │   ├── developer_agent.py
│   │   ├── testing_agent.py
│   │   └── security_agent.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py            # Tool base + Registry
│   │   ├── read_tools.py      # read_state, read_issue, read_docs, read_repo, grep
│   │   ├── write_tools.py     # write_audit, update_memory, create_patch, exec_terminal
│   │   └── analysis_tools.py  # run_tests, static_analysis, detect_injection
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py          # LLMClient (chat.iaedu.pt — GPT-5.5)
│   └── mocks/
│       ├── __init__.py
│       ├── git_repo.py        # Repositório Git simulado (sistema de ficheiros)
│       └── llm.py             # Respostas fixas do LLM para demonstração sem API
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Matriz de Permissões

Respeita estritamente a matriz do relatório. Cada agente tem ferramentas autorizadas específicas:

| Agente | Ferramentas Autorizadas |
|--------|------------------------|
| Orchestrator | `read_state`, `write_audit`, `update_memory`, `request_approval` |
| Requirements | `read_issue`, `read_docs` |
| Architecture | `read_repo`, `grep` |
| Developer | `read_repo`, `create_patch`, `exec_terminal` (com aprovação) |
| Testing | `read_repo`, `run_tests` |
| Security | `read_repo`, `static_analysis`, `detect_injection` |

### Cadeia de validação de `exec_terminal`

1. **Validar o agente** — Confirma que o agente solicitante tem permissão para `exec_terminal` (apenas Developer)
2. **Validar os argumentos** — Verifica se os argumentos são válidos e seguros
3. **Verificar allowlist de comandos** — Apenas comandos pré-aprovados são executados
4. **Solicitar aprovação humana** — Pausa a execução e pede confirmação ao utilizador
5. **Confirmação dupla** — Para operações destrutivas, exige confirmação adicional
6. **Executar e registar** — Executa o comando e regista o resultado no Audit Log

## Troca entre Agentes

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

## Ferramentas Python

| Finalidade | Ferramenta | Uso |
|------------|-----------|-----|
| **Interface** | `textual` | TUI moderna com widgets, layout, CSS |
| **Leitura de ficheiros** | `pypdf` | Extrair texto de PDFs (Issues, documentação) |
| **Leitura de ficheiros** | `pathlib` | Manipulação de caminhos e leitura de ficheiros |
| **Serialização** | `dataclasses-json` | Serializar/deserializar `Issue`, `ChangeSet`, `AuditEntry`, `ASFState` |
| **LLM** | `openai` | Cliente para API do `chat.iaedu.pt` (GPT-5.5) |
| **Configuração** | `python-dotenv` | Carregar credenciais do `.env` |
| **YAML config** | `PyYAML` | Ficheiros de configuração |

## LLM — chat.iaedu.pt

O protótipo utiliza a API do **chat.iaedu.pt** com o modelo **GPT-5.5** (via OpenAI SDK, compatível com endpoint customizado).

- **Endpoint:** `https://chat.iaedu.pt` (configurável via `.env`)
- **Autenticação:** Chave de API no ficheiro `.env`
- **Fallback:** Implementação de `llm/mock/llm.py` com respostas fixas para demonstração sem credenciais

## Interface — Textual (TUI)

A interface principal é uma **TUI Textual** com os seguintes elementos:

- **Sidebar** (esquerda): Lista de execuções (`ExecutionList`)
- **Área principal** (direita): Log/Chat em tempo real (`ChatLog`)
- **Input** (base): Campo de texto para submissão de Issues ou comandos
- **Keybindings**:
  - `Enter`: submeter texto
  - `Ctrl+Q`: sair da aplicação
  - `Ctrl+C`: cancelar operação em curso

### Fluxo típico:
1. Usuário digita uma Issue no campo de input
2. Pressiona `Enter`
3. O TUI cria uma nova execução e mostra no sidebar
4. Mensagens de cada agente aparecem no chat em tempo real
5. Ao final, o estado é atualizado e o log mostra o resultado

### Fluxo simulado (exemplo):
```
[Orchestrator] A classificar a Issue e delegar...
[Requirements] A interpretar a Issue e derivar requisitos...
[Architecture] A planear a execução e decompor em tarefas...
[Developer] A gerar o ChangeSet (patch)...
[Testing] A derivar e executar testes...
[Security] A auditar a segurança da alteração...
[Review] A revisar a alteração final...
✅ Execução concluída com sucesso!
```

## Instalação e Execução

```bash
# 1. Clonar o repositório
git clone https://github.com/franciscocosta4/asf.git
cd asf

# 2. Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente (opcional para protótipo com mock)
cp .env.example .env
# Editar .env com a chave da API chat.iaedu.pt (opcional)

# 5. Executar a TUI
python -m asf.main
```

### `requirements.txt` (planeado)

```
textual
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

## Ligações

- **Repositório GitHub:** https://github.com/franciscocosta4/asf.git
- **Relatório do projeto:** `trabalho-eng.software (1).pdf` (Secção 7 — Protótipo)
- **Curso:** Engenharia de Informática, Universidade de Trás-os-Montes e Alto Douro

## Licença

MIT License — veja o ficheiro `LICENSE` (se aplicável).