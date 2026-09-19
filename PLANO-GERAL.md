# TailaBot - RemoteCoding — Plano Telegram ↔ opencode

> Última atualização: 2026-09-19
> Status: **Fase 1 em produção** — bridge corrigido (fix `--attach` v1.18.x em 2026-09-19);
> respostas reais funcionando; pendente reteste do dono pelo Telegram.
> Nome de trabalho: **TailaBot - RemoteCoding** · Persona do bot: **Taila** (a IA do Telegram do dono).

---

## 1. Visão

O dono quer controlar o opencode (e, pelo opencode, os projetos da AAA Digital) **pelo Telegram**,
com **liberdade total de menus e botões inline** — sem amarras de um framework pronto de "runner".
Ou seja: **um bot Telegram dedicado**, criado via BotFather, que funciona como *frontend* de texto
e botões para o motor (o opencode). Chamamos isso de **TailaBot - RemoteCoding** (a **Taila**,
persona/gpt do Telegram do dono, virou a "remote coder").

> 📁 **Localização**: este projeto vive DENTRO do diretório de bots Telegram do dono
> (`AAA TBOT 00 GENERAL 2026 - XPS/TBot-TailaBot/`), como um **projeto Python separado** —
> tudo de Telegram fica junto na pasta de bots; o TailaBot-RemoteCoding tem venv/config próprios.

O bot deve poder, por exemplo:

- Rodar tarefas do tipo "edita tal arquivo", "roda os testes do projeto X", "o que fizemos até hoje?"
  e devolver **texto + screenshot** (Playwright MCP) + **ZIP** quando aplicável + **link**.
- Ter **menus inline próprios** (teclado inline com projetos, ações frequentes, confirmação de
  tarefas destrutivas tipo `rm`/deploy).
- Restringir acesso **só ao dono** (allowlist por `chat_id`).
- Funcionar primeiro **local** (PC do dono, mesmo host do opencode) e depois evoluir para a VPS.

## 2. Motivação / contexto

- Já existe experiência do dono com **TBot/TailaBot (Telethon)** e **AIZA Bot** (`AAA PROJETO AIZA Bot/`) —
  mas o projeto novo é **dedicado** e feito sob medida (maioria dos "telegram coders" prontos
  travam o modelo/menus; o dono quer comandos 100% livres). A mesma "Taila" que comanda o Telegram
  geral ganha aqui o papel de *remote coding*.
- O opencode já tem **3 MCP servidores** instalados globalmente (`playwright`, `memory`,
  `sequential-thinking`) — ver `MCP project/mcp-config.md`. O screenshot virá do MCP do Playwright.
- **Regra anti-credencial**: NENHUM token em MD/README/código. Token do bot vai em `.env` (não
  versionado) ou é pedido na hora.

## 3. Arquitetura (alvo)

```
        Telegram (dono)
             │  events (update)
             ▼
   [Bot aiogram 3.x — Python]  ←  BOT_TOKEN (BotFather), OWNER_CHAT_ID
        │  (menus inline próprios; valida chat_id)
        │  enfileira "tarefa" (texto/arquivo/anexo)
        ▼
   [opencode run --format json --dir <workdir>]   ← opencode no mesmo PC (direto, SEM --attach)
        │  (+ --session p/ continuar a conversa; + --model explícito)
        ▼
   resultado (texto final / arquivos alterados prontos)
        │
        ├── texto: resumo da resposta do agente (última mensagem)
        ├── screenshot (Playwright MCP) quando a tarefa for de UI/página
        ├── ZIP da pasta alterada (opcional, botão inline)
        └── link (ex.: URL do site/página testada)
        ▼
   Resposta ao dono no mesmo chat (texto + document/file + botões)
```

### Porta: 4590 (fixa, evitando conflito com o 8080/8794 usados nos testes locais)

## 4. Stack escolhida (decisões já tomadas)

| Componente | Escolha | Motivo |
|---|---|---|
| Bot | **aiogram 3.x** (Python) | Async, filters, Keyboards inline/disposal, menus livres; sem lock-in |
| Bridge | `opencode run --format json --dir <workdir>` (+ `--session`/`--model`) | Sessões persistentes no `opencode.db` + saída JSON parseável; **sem `--attach`** (bug v1.18.x) |
| Screenshot | **Playwright MCP** (já instalado global) | Página testada → imagem enviada no chat |
| ZIP | `python -m zipfile` / `shutil.make_archive` | Entrega de entregáveis (ex.: cliente) |
| Estado persistente | SQLite / JSON em disco (ex.: `telecomando_state.json`) | Histórico de tarefas, sessões ativas |
| Segurança | `.env` (BOT_TOKEN, OWNER_CHAT_ID) + allowlist `chat_id` | Só o dono comanda; anti-credencial |

> ⚠️ **Flags do opencode ATUALIZADO em 2026-09-19 (v1.18.31)**: o `opencode run --attach <url>`
> **não repassa eventos de texto** (emite só `step_start` e encerra) — as respostas do bot vinham
> sempre `"(sem resposta de texto)"`. O `opencode_bridge.py` agora chama `opencode run --format json
> --dir <workdir>` **direto** (+ `--session` p/ continuar conversa, `--model` explícito): o evento
> `type:"text"` chega normalmente e a sessão persiste no mesmo `opencode.db`. O servidor na 4590
> deixou de ser necessário para as tarefas (mantido p/ `/status`).

## 5. Menus inline planejados (botões)

> Implementado no código (2026-09-08) — menu **organizado e interativo** no `tailabot_remote.py`:

1. **Menu principal**: `📁 Projetos` · `✍️ Perguntar` · `⚙️ Ações` · `🔁 Repetir última` · `🔄 Status` · `🛟 Ajuda`
2. **📁 Projetos** → Funil TikTok / Life Maps / Disparo em Massa / Loja BlackOps7; cada projeto abre
   **ações óbvias** (ex.: "▶️ Rodar test-motor 13/13", "🌈 ZIP do funil", "▶️ pytest", "📋 Resumo").
3. **⚙️ Ações** → "❓ O que fizemos até hoje?" (lê os MDs via opencode), ZIP do funil, screenshot, status.
4. **Confirmação obrigatória** para ações destrutivas (deploy, renames, apagar arquivos):
   botão `⚠️ Confirmo` / `❌ Cancelar` (a implementar com as ações destrutivas).

## 6. Fluxo de uma tarefa (exemplo: "zípar o funil")

1. Dono envia texto no chat (ou toca botão `📦 ZIP do funil`).
2. Bot valida `chat_id`; mostra `⏳ aguarde…` com `with_status`.
3. Bot chama o bridge (`opencode run` numa sessão) com a instrução pré-montada.
4. Ao terminar: envia **texto-resumo** + **arquivo ZIP** (se gerado) + botões de menu.
5. Erros: mostra `❌ <mensagem>` e mantém o menu (não mata a sessão).

## 7. Fases

> **Atualização 2026-09-10**: Fase 1 **funcional** — `OPENCODE_MODEL=bigpickle-zen/big-pickle`
> adicionado ao `.env` e propagado nas chamadas do bridge (modelo OpenRouter/`auto` oficial estava
> sem endpoints de tool use; `google/gemini-2.5-flash` da OpenRouter sem créditos → 402). Parser do
> bridge corrigido para o formato real dos eventos (`type:"text"`/`tool_use`/`error` + `sessionID` no
> topo) — antes retornava "(sem resposta de texto)". Notificações de progresso em tempo real
> implementadas (`on_progress` no bridge + throttle ~4s no chat). Texto do `/start` alterado a pedido
> do dono para **"Taila Bot 🙋♀️ - RC / Opencode - My Big Pickle"**. Bot relançado (allowlist ativo),
> servidor 4590 online.

> **FIX 2026-09-19 (v1.18.31)**: com `--attach` o `run` emite só `step_start` → bot respondia sempre
> "(sem resposta de texto)" (ver seção 4). `opencode_bridge.py` trocado para `opencode run` **direto**
> (sem `--attach`), com `--dir`=WORK_ROOT, `--model` e `--session` p/ continuidade. Validado
> ponta-a-ponta: resumo dos MDs (615 chars) e conversa com continuidade (`--session` → resposta real).
> **Bot relançado** em 2026-09-19; servidor 4590 reiniciado com o binário atual (o antigo processos
> pré-1.18 causava `426 OpenCode 1.18.0+ required`).

### Fase 0 — Preparo (este documento)
- [x] Dono **criou o bot no BotFather** (`@TailaBot_RemoteCoding_bot`) e o `chat_id` (allowlist).
- [x] `.env` preenchido: `BOT_TOKEN`, `OWNER_CHAT_ID`, `WORK_ROOT`, `OPENCODE_BASE_URL/SERVE_PORT`, `OPENCODE_MODEL`.
- [x] Definição de stack/arquitetura/menus (este MD).
- [x] Pasta criada **dentro do diretório de bots Telegram** (`TBot-TailaBot/TailaBot-RemoteCoding/`)
      como projeto Python separado (AGENTS, README, env de exemplo).
- [x] **Flags do opencode validados**: `run --format json --dir <workdir> --session --model`
      (v1.18.31; `--attach` NÃO repassa texto — ver seção 4).
- [ ] Dono abrir o **BotFather** e criar o bot → colar o **BOT_TOKEN** (na hora, sem gravar
      nos MDs) e o **próprio `chat_id`** (via `@userinfobot` ou primeira mensagem ao bot).
      → Instruções passo a passo no `README.md`.

### Fase 1 — Bridge funcional (local)
- [x] Validar `opencode run --format json` (v1.18.31; descartado `--attach` que não repassa texto).
- [x] Código base: `tailabot_remote.py` (aiogram) + `opencode_bridge.py` (subprocess por arquivo,
      sem pipe deadlock) + `check_chat_id.py` + `requirements.txt`.
- [x] **Menu inline organizado e interativo** (Projetos → ações rápidas locais; Ações; Perguntar; Repetir; Status).
- [x] **Bot rodando**: `/start` (2º teste OK, allowlist ativo), texto → sessão opencode → resposta.
- [x] **Modelo explícito** no bridge (`OPENCODE_MODEL`) + **parser de eventos reais** + **progresso em tempo real**.
- [x] `pip install -r requirements.txt` (venv) + `.env` preenchido pelo dono.
- [ ] Encaminhar `document`/arquivo (ex.: `.pdf`, `.md`) para a sessão (handler pronto; testar com token).

### Fase 2 — Menus + screenshot + ZIP
- [ ] Menus inline da seção 5 (projetos, ações, confirmação destrutiva).
- [ ] Screenshot via **Playwright MCP** (servidor já global; chamar pelo mesmo mecanismo que o opencode).
- [ ] ZIP de pastas e envio como documento.
- [ ] Estado (sessões ativas, última tarefa) em `tailabot_state.json`.

### Fase 3 — Robustez e deploy
- [ ] Timeouts, fila (1 tarefa por vez por chat), log em SQLite.
- [ ] Rodar na VPS Hostinger (`148.230.78.83`) como serviço (systemd/Docker) — opcional,
      já que o opencode precisa rodar no mesmo host.
- [ ] Migrar para webhook (em vez de polling) se subir em VPS.

## 8. Segurança (regras duras)

- **Anti-credencial**: token e chat_id SÓ em `.env` do dono; jamais em MDs, código ou log.
- **Allowlist**: mensagens de qualquer `chat_id` fora do `OWNER_CHAT_ID` são ignoradas (log).
- Não expor caminhos absolutos desnecessários do PC do dono ao responder (ofuscar bases).
- Comandos destrutivos exigem **confirmação inline** e só rodam com aprovação no próprio chat.

## 9. Pendências / decisões para o dono

1. **Criar o bot no BotFather** e colar token + chat_id (é o único bloqueio da Fase 1) — instruções no `README.md`.
   - Nome exibido: **Taila Bot** · Descrição/About: **RemoteCoding** (definidos).
2. Validar o sufixo/forma de resposta preferida (texto puro × markdown × HTML do Telegram).
3. Depois do MVP local: subir para a VPS ou manter no PC? (afeta polling × webhook).
4. **Anotado como pendente (a fazer depois)**: correções finas e "nomes descritivos" no código/bridge
   (ex.: refino de parser de saída JSON, renomear funções/variáveis para nomes descritivos). Não bloqueia o MVP.