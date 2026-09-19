# AGENTS.md — TailaBot - RemoteCoding (bot Telegram ↔ opencode)

> Diretrizes para o opencode (e qualquer agente) trabalhar nesta pasta.
> Regra-mãe: ver `AGENTS.md` raiz do projeto ("AAA digital PROJECT") e o
> `AGENTS.md` do pai `TBot-TailaBot/` (diretório de bots Telegram).

## O que é

Um **bot Telegram dedicado** (aiogram 3.x, Python) que funciona como *frontend* de texto/botões
para o opencode — o dono pede tarefas pelo celular e o opencode executa no PC (depois na VPS).
**Nome do projeto: TailaBot - RemoteCoding**; a persona/nome da IA é **Taila** (a IA do Telegram
do dono — como Aiza é a do WhatsApp).

## Estado atual

- **Fase 1 em produção**: bot rodando (`/start`, menus inline, allowlist ativo) com respostas reais
  do opencode (`bigpickle-zen/big-pickle`) e **log remoto persistente** (`REMOTE_LOG.md`).
- **Teste real do dono PASSOU (2026-09-19)**: bot acessado pelo Telegram do dono, menus inline
  respondendo. **Git (2026-09-19)**: repo standalone público `DSama-lab/TailaBot-RemoteCoding`,
  branch `main`, tag+release **v1.0.0**. `README.md` é o README formal em inglês (portfólio).
- Todo comando/arquivo/teste executado via Telegram fica registrado no `REMOTE_LOG.md`.

### ⚠️ FIX 2026-09-19 — não usar `--attach` (opencode v1.18.x)

O `opencode run --attach <url>` na v1.18.31 **emite só `step_start` e encerra sem repassar os
eventos de texto ao CLI** → o bot respondia "(sem resposta de texto)". O `opencode_bridge.py`
agora chama `opencode run --format json --dir <workdir> [--session <id>] [--model <m>]` **direto**
(sem `--attach`): os eventos `type:"text"` chegam normalmente e a continuidade de sessão via
`--session` funciona (mesmo storage `opencode.db`). O servidor na 4590 não é mais necessário para
as tarefas (mantido opcional p/ `/status`).

## Regras obrigatórias

1. **Anti-credencial (severidade máxima):** nenhum token de bot, chat_id ou chave de API em MDs,
   código-fonte ou config. Só variáveis de exemplo em `.env.example`. Valores reais vão no `.env`
   do dono (não versionado) ou são pedidos na hora.
2. **Não inventar flags do opencode.** A bridge usa `opencode run --format json --dir <workdir>`
   direto (sem `--attach`) + `--session` p/ continuidade. Sempre conferir a versão instalada
   (`opencode --version`) antes de mudar.
3. **Respeitar o allowlist** (`OWNER_CHAT_ID`): qualquer chat fora da lista é ignorado.
4. Ações destrutivas (deploy, apagar, renomear em massa) precisam de **confirmação inline**.
5. Ao trabalhar aqui, manter coerência com os outros projetos: ler `MDs Projects/_INDEX_MASTER.md`
   se o bot for mexer nos projetos reais.
6. **Pendente (não fazer agora)**: correções finas e "nomes descritivos" no código/bridge — só
   depois que o MVP estiver rodando com o token real.
7. Ao finalizar tarefa, atualizar: `PLANO-GERAL.md` (status/fases) e o `MDs Projects/_INDEX_MASTER.md`.

## Arquivos

| Arquivo | Papel |
|---|---|
| `README.md` | **README formal em inglês** (portfólio). Como rodar + instruções de criação do bot no BotFather + arquitetura + roadmap |
| `.gitignore` | Exclui `.env`, `.venv/`, `__pycache__/`, `*.log`, `rotina.snap.json`, `REMOTE_LOG.md`, `_pb_test.*` |
| `.env.example` | Variáveis de exemplo (nunca valores reais) |
| `requirements.txt` | Dependências Python |
| `tailabot_remote.py` | Bot aiogram 3.x (allowlist, comandos, menus) |
| `opencode_bridge.py` | Bridge: sobe `opencode serve` (se preciso) e roda `opencode run --attach --format json` |
| `remote_log.py` | Log persistente do RemoteCoding (escreve no `REMOTE_LOG.md` + CLI de resumo) |
| `REMOTE_LOG.md` | **Acompanhar**: registro de tudo que o dono faz via Telegram (resumir onde paramos) |
| `rotina.py` / `rotina.bat` / `instalar-rotina.bat` | Rotina local de avisos/recados (prefira nomes neutros; ver `.env` p/ remoto) |
| `rotina.log` / `rotina.snap.json` | Registro e estado da rotina local |
| `AGENTS.md` | Este arquivo |

## Como retomar

1. Confirmar que o `.env` tem `BOT_TOKEN` + `OWNER_CHAT_ID` (o dono já preencheu).
2. `python -m venv .venv` + `pip install -r requirements.txt` (aiogram 3.x + python-dotenv).
3. `start_tailabot.bat` (detached; logs em `bot_run.log`/`bot_run.err.log`). O bridge usa
   `opencode run` direto — **não precisa** do servidor na 4590.
4. Testar `/start` e uma tarefa de texto (`.env` já tem `OPENCODE_MODEL=bigpickle-zen/big-pickle`).

## Log remoto (REMOTE_LOG.md)

- O dono pede tarefas pelo Telegram e o PC só processa quando chega comando (polling leve;
  nada é repetido/enviado por conta própria).
- Tudo que roda via Telegram (tarefa, botão, arquivo, teste local, ZIP) é anexado ao
  `REMOTE_LOG.md` nesta pasta — é onde o opencode **retoma o fio** ao dono chegar no PC:
  `python remote_log.py` (últimos 10) · `last N` · `full` · `grep TERMO`.
- Anti-credencial: o log nunca contém token/chat_id/segredos; só prompts e respostas.