import asyncio
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ContentType
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from dotenv import load_dotenv

import opencode_bridge as bridge
import remote_log

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "0") or 0)
BASE_URL = os.getenv("OPENCODE_BASE_URL", "http://127.0.0.1:4590")
PORT = int(os.getenv("OPENCODE_SERVE_PORT", "4590"))
MODEL = os.getenv("OPENCODE_MODEL", "") or None
WORK_ROOT = Path(os.getenv("WORK_ROOT", ""))
MSG_FORMAT = os.getenv("MSG_FORMAT", "text")
TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT_SECS", "600"))

router = Router()
pending_file = {}
last_task = {}
chats_vistos = {}
serve_proc = None


@router.message.middleware()
async def log_who(handler, mw_message: Message, data):
    if not is_owner(mw_message.chat.id):
        who = mw_message.from_user.full_name if mw_message.from_user else "?"
        print(f"[taila] msg de chat nao autorizado -> chat_id={mw_message.chat.id} (sender={who})", flush=True)
        agora = time.monotonic()
        if agora - chats_vistos.get(mw_message.chat.id, 0) > 3600:
            chats_vistos[mw_message.chat.id] = agora
            try:
                await mw_message.bot.send_message(OWNER_CHAT_ID, f"Registro de rotina: atividade em chat externo (id {mw_message.chat.id}, {who}).")
            except Exception:
                pass
    return await handler(mw_message, data)

G = {
    "funil": (WORK_ROOT / "clientes" / "funil-ofertatiktok", "Funil TikTok"),
    "mapa": (WORK_ROOT / "MAPA VETORIAL VIAJENS", "Life Maps"),
    "disparo": (WORK_ROOT / "Disparo em Massa Project", "Disparo em Massa"),
    "loja": (Path(os.getenv("LOJA_PATH", r"C:\xampp\htdocs\blackops7")), "Loja BlackOps7"),
}

EMOJI = {
    "funil": "Funil",
    "mapa": "Mapa",
    "disparo": "Disparo",
    "loja": "Loja",
    "dia": "Dia",
    "teste": "Teste",
    "zip": "Zip",
    "shot": "Shot",
    "consulta": "[consulta]",
    "executa": "[executa]",
}

PROMPTS = {
    "funil_res": "Dê um resumo executivo do funil TikTok (clientes/funil-ofertatiktok) lendo o README e o RELATORIO.",
    "mapa_res": "Rode o motor do Life Maps: `node test-motor.js` em MAPA VETORIAL VIAJENS e reporte o resultado (13/13).",
    "disparo_res": "Resumo executivo do projeto Disparo em Massa Project (estado, arquivos, testes).",
    "loja_res": "Resumo do estado da loja BlackOps7 (tema GTA6, produtos de teste, homologação).",
    "dia": "Resuma a última sessão de trabalho: leia MDs Projects/_INDEX_MASTER.md e AGENTS.md e responda 'o que fizemos até hoje?'. Seja curto e direto.",
}

TXT = {
    "welcome": (
        "Taila Bot - RC\n"
        "Opencode - My Big Pickle\n\n"
        "Oi! Sou o RemoteCoding da AAA Digital: voce manda a funcao e eu executo no PC\n"
        "(via opencode). Use os botoes do menu abaixo ou digite qualquer tarefa.\n\n"
        "Marcadores (no inicio da mensagem):\n"
        "- ? ou plan: so consulta (nao altero nada)\n"
        "- ! ou build: executo a tarefa"
    ),
    "ask": "Digite sua pergunta/tarefa direto no chat (ex.: \"zipa o funil\", \"roda os testes do mapa\").",
    "busy": "Aguarde, Taila trabalhando...",
    "done": "Pronto! Mais alguma coisa?",
    "err": "Erro:",
    "timeout": "Demorou demais. Tente de novo.",
    "no_last": "Nada para repetir ainda.",
    "doc": "Arquivo recebido. Agora mande a instrucao para processa-lo.",
    "offline": "opencode offline - rode: opencode serve --port {port}",
    "projects": "Projetos da AAA Digital - escolha para ver acoes.",
}


def kb(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows])


MAIN_KB = kb(
    [("Projetos", "m:proj"), ("Perguntar", "m:ask")],
    [("Acoes", "m:act"), ("Repetir ultima", "m:rep")],
    [("Ajuda", "m:help"), ("Status", "m:st")],
)

PROJ_KB = kb(
    [("Funil TikTok", "p:funil"), ("Life Maps", "p:mapa")],
    [("Disparo em Massa", "p:disparo"), ("Loja BlackOps7", "p:loja")],
    [("Menu", "m:home")],
)

ACT_KB = kb(
    [("O que fizemos ate hoje?", "a:dia")],
    [("ZIP do funil", "a:zip_funil"), ("Screenshot", "a:shot")],
    [("Repetir ultima", "m:rep"), ("Status", "m:st")],
    [("Voltar", "m:home")],
)


def proj_kb(key):
    rows = []
    if key == "funil":
        rows = [[("ZIP do funil", "a:zip_funil")], [("Resumo", "f:funil_res")]]
    elif key == "mapa":
        rows = [[("Rodar test-motor (13/13)", "f:mapa_test")], [("Resumo", "f:mapa_res")]]
    elif key == "disparo":
        rows = [[("Rodar pytest", "f:disparo_test")], [("Resumo", "f:disparo_res")]]
    elif key == "loja":
        rows = [[("Resumo", "f:loja_res")]]
    rows.append([("Voltar", "m:proj"), ("Menu", "m:home")])
    return kb(*rows)


def is_owner(chat_id):
    return OWNER_CHAT_ID > 0 and chat_id == OWNER_CHAT_ID


async def send_long(message, text, kbk=None):
    for i in range(0, len(text), 4000):
        await message.answer(text[i : i + 4000], reply_markup=kbk if (i + 4000 >= len(text)) else None, parse_mode="HTML" if MSG_FORMAT == "html" else None)


def parse_mode():
    return "HTML" if MSG_FORMAT == "html" else "Markdown"


async def answer_state(cb, text):
    await cb.message.edit_text(text, parse_mode=parse_mode())
    await cb.answer()


async def run_ai_and_report(anchor, prompt, kbk=None, mark="[proc]"):
    print(f"[taila] acao: {prompt[:120]} | mark={mark}", flush=True)
    busy = await anchor.answer(TXT["busy"])
    last_prog = {}
    loop = asyncio.get_running_loop()

    def on_progress(marker):
        nonlocal last_prog
        now = time.monotonic()
        if last_prog and now - last_prog["t"] < 4 and last_prog["m"] == marker:
            return
        last_prog = {"t": now, "m": marker}

        async def _send():
            try:
                await anchor.answer(f"Taila: {marker}", parse_mode=None)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(_send(), loop)

    try:
        r = await asyncio.to_thread(
            bridge.run_task,
            prompt,
            BASE_URL,
            str(WORK_ROOT),
            timeout=TASK_TIMEOUT,
            on_progress=on_progress,
            model=MODEL,
        )
        if not r["ok"] and ("offline" in r["text"].lower() or "refused" in r["raw"].lower()):
            await busy.delete()
            remote_log.append("acao", prompt, False, text=r["text"], error="opencode offline")
            await anchor.answer(TXT["offline"].format(port=PORT))
            return
        text = r["text"] or "(sem resposta)"
    except subprocess.TimeoutExpired:
        await busy.delete()
        remote_log.append("acao", prompt, False, error="timeout")
        await anchor.answer(TXT["timeout"])
        return
    await busy.delete()
    print(f"[taila] acao fim ok={r['ok']} len={len(text)}", flush=True)
    remote_log.append("acao", prompt, r["ok"], session_id=r["session_id"], text=text)
    await send_long(anchor, f"{mark} {text}".strip(), kbk)
    if not kbk:
        await anchor.answer(TXT["done"], reply_markup=MAIN_KB)


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_owner(message.chat.id):
        return
    await message.answer(TXT["welcome"], reply_markup=MAIN_KB, parse_mode=None)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    if not is_owner(message.chat.id):
        return
    await message.answer(TXT["welcome"], reply_markup=MAIN_KB, parse_mode=None)


@router.message(Command("status"))
async def cmd_status(message: Message):
    if not is_owner(message.chat.id):
        return
    up = bridge.server_is_up(BASE_URL)
    txt = f"opencode ({BASE_URL}): " + ("on-line" if up else "off-line - rode: opencode serve --port %d" % PORT)
    await message.answer(txt, reply_markup=MAIN_KB)


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_owner(message.chat.id):
        return
    await message.answer(
        "Comandos:\n"
        "/start · /menu — abrir menu\n"
        "/status — servidor opencode\n"
        "/help — esta ajuda\n\n"
        "Marcadores: ? ou plan: = so consulta · ! ou build: = executar\n"
        "Ex.: \"? como esta a loja\" · \"! roda os testes do mapa\"\n"
        "Ou use o menu Acoes / Projetos. Digite \"o que fizemos ate hoje?\" p/ resumo do dia.",
        reply_markup=MAIN_KB,
    )


@router.message(F.content_type == ContentType.DOCUMENT)
async def got_document(message: Message):
    if not is_owner(message.chat.id):
        return
    file = await message.bot.get_file(message.document.file_id)
    dest = WORK_ROOT / ".tailabot_tmp" / message.document.file_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    await message.bot.download_file(file.file_path, destination=dest)
    pending_file[message.chat.id] = str(dest)
    await message.answer(TXT["doc"])


@router.message(F.text)
async def handle_text(message: Message):
    chat_id = message.chat.id
    if not is_owner(chat_id):
        return
    prompt = message.text.strip()
    if not prompt or prompt.startswith("/"):
        return
    consulta = False
    m = re.match(r"^\s*(?P<tag>\?|!|\b(?:plan|build|consulta|executar)\b)[\s:.\-]*", prompt, re.IGNORECASE)
    if m:
        tag = m.group("tag").lower()
        prompt = prompt[m.end():].strip()
        if tag in ("?", "plan", "consulta"):
            consulta = True
        if not prompt:
            await message.answer("…e a tarefa? Depois do marcador, digite o que quer.")
            return
    prompt_use = prompt
    if consulta:
        prompt_use += "\n\n[Modo consulta: analise e responda apenas, pesquise o que precisar; NAO altere, crie ou delete arquivos, nem execute comandos que mudem estado.]"
    files = []
    pf = pending_file.pop(chat_id, None)
    if pf:
        files.append(pf)
    print(f"[taila] tarefa recebida: {prompt[:120]} | consulta={consulta} | arquivo={pf}", flush=True)
    busy = await message.answer(TXT["busy"])
    last = last_task.get(chat_id, {})
    last_prog = {}
    loop = asyncio.get_running_loop()

    def on_progress(marker):
        nonlocal last_prog
        now = time.monotonic()
        if last_prog and now - last_prog["t"] < 4 and last_prog["m"] == marker:
            return
        last_prog = {"t": now, "m": marker}

        async def _send():
            try:
                await message.answer(f"Taila: {marker}", parse_mode=None)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(_send(), loop)

    try:
        result = await asyncio.to_thread(
            bridge.run_task,
            prompt_use,
            BASE_URL,
            str(WORK_ROOT),
            session_id=last.get("session_id"),
            files=files or None,
            timeout=TASK_TIMEOUT,
            on_progress=on_progress,
            model=MODEL,
        )
    except subprocess.TimeoutExpired:
        await busy.delete()
        remote_log.append("tarefa", prompt, False, error="timeout")
        await message.answer(TXT["timeout"])
        return
    await busy.delete()
    last_task[chat_id] = {"prompt": prompt, "session_id": result["session_id"]}
    print(f"[taila] tarefa fim ok={result['ok']} len={len(result['text'] or '')}", flush=True)
    remote_log.append("tarefa", prompt, result["ok"], session_id=result["session_id"], text=result["text"], extra=files or None)
    mark = EMOJI["consulta"] if consulta else EMOJI["executa"]
    resp = f"{mark} {result['text']}".strip() if result["text"] else "(sem resposta)"
    await send_long(message, resp, MAIN_KB)


@router.callback_query(F.data.startswith("m:"))
async def cb_menu(cb: CallbackQuery):
    act = cb.data[2:]
    if act == "home":
        await cb.message.edit_text(TXT["welcome"], reply_markup=MAIN_KB, parse_mode=None)
    elif act == "proj":
        await cb.message.edit_text(TXT["projects"], reply_markup=PROJ_KB, parse_mode=parse_mode())
    elif act == "act":
        await cb.message.edit_text("Acoes rapidas:", reply_markup=ACT_KB, parse_mode=parse_mode())
    elif act == "help":
        await cb.message.edit_text("Use os botoes: Projetos (acoes por projeto) · Acoes (resumo do dia, ZIP, screenshot) · ou digite qualquer tarefa.", reply_markup=MAIN_KB, parse_mode=parse_mode())
    elif act == "ask":
        await cb.answer("Digite a tarefa no chat.")
        await cb.message.answer(TXT["ask"])
    elif act == "rep":
        last = last_task.get(cb.message.chat.id)
        if not last:
            await cb.answer(TXT["no_last"], show_alert=True)
            return
        await cb.message.answer(f"Repetindo: {last['prompt']}")
        await run_ai_and_report(cb.message, last["prompt"])
    elif act == "st":
        up = bridge.server_is_up(BASE_URL)
        await cb.answer(("opencode: on-line" if up else "opencode: off-line"), show_alert=True)
    await cb.answer()


@router.callback_query(F.data.startswith("p:"))
async def cb_proj(cb: CallbackQuery):
    key = cb.data[2:]
    path, name = G.get(key, (None, key))
    await answer_state(cb, f"**{name}**\n`{path}`\n\nEscolha uma acao:")
    await cb.message.edit_reply_markup(reply_markup=proj_kb(key))


@router.callback_query(F.data.startswith("f:"))
async def cb_fact(cb: CallbackQuery):
    key = cb.data[2:]
    if key == "mapa_test":
        await answer_state(cb, "Rodando test-motor...")
        r = bridge.run_local(["node", "test-motor.js"], str(G["mapa"][0]), timeout=120)
        remote_log.append("local", "node test-motor.js (Life Maps)", r["ok"], text=r["text"])
        await cb.message.answer(f"test-motor.js\n\n{r['text'][-2500:]}", reply_markup=proj_kb("mapa"))
    elif key == "disparo_test":
        await answer_state(cb, "Rodando pytest...")
        r = bridge.run_local(["python", "-m", "pytest", "-q"], str(G["disparo"][0]), timeout=180)
        remote_log.append("local", "pytest (Disparo em Massa)", r["ok"], text=r["text"])
        await cb.message.answer(f"pytest\n\n{r['text'][-2500:]}", reply_markup=proj_kb("disparo"))
    else:
        prompt = PROMPTS.get(key, "Resuma esse projeto da AAA Digital.")
        await answer_state(cb, "Resumindo...")
        proj = key.split("_")[0]
        await run_ai_and_report(cb.message, prompt, proj_kb(proj), mark=EMOJI.get(proj, "[proc]"))


@router.callback_query(F.data.startswith("a:"))
async def cb_act(cb: CallbackQuery):
    key = cb.data[2:]
    if key == "dia":
        await answer_state(cb, "Lendo MDs...")
        await run_ai_and_report(cb.message, PROMPTS["dia"], MAIN_KB, mark=EMOJI["dia"])
    elif key == "shot":
        await answer_state(cb, "Mande a URL que quer que eu screenshot (Playwright MCP).")
    elif key == "zip_funil":
        await answer_state(cb, "Gerando ZIP do funil...")
        src = G["funil"][0]
        dst = src.with_suffix(".zip")
        try:
            out = bridge.zip_folder(str(src), str(dst))
            remote_log.append("local", "ZIP do funil", True, text=f"gerado: {out}")
            await cb.message.answer_document(BufferedInputFile(Path(out).read_bytes(), filename="funil-ofertatiktok.zip"))
            await cb.message.answer(TXT["done"], reply_markup=MAIN_KB)
        except Exception as e:
            remote_log.append("local", "ZIP do funil", False, error=str(e))
            await cb.message.answer(f"{TXT['err']} {e}", reply_markup=MAIN_KB)


async def main():
    global serve_proc
    if not BOT_TOKEN:
        print("[taila] ERROR: configure BOT_TOKEN no .env (veja README.md).")
        sys.exit(1)
    discovery = OWNER_CHAT_ID <= 0
    if discovery:
        print("[taila] MODO DESCOBERTA (OWNER_CHAT_ID vazio): ninguem responde, mas todo chat e logado.")
        print("[taila] Mande /start para o bot no Telegram e leia o chat_id no console/log. Depois ponha no .env.")
    if not bridge.server_is_up(BASE_URL):
        print(f"[taila] opencode offline - subindo servidor na porta {PORT}...")
        serve_proc = bridge.start_server(PORT)
        if not bridge.wait_for_server(BASE_URL):
            print(f"[taila] aviso: nao consegui subir o servidor em {BASE_URL}. Rode manualmente: opencode serve --port {PORT}")
            serve_proc = None
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()
    dp.include_router(router)
    print("[taila] Taila Bot rodando" + (f" | chat autorizado: {OWNER_CHAT_ID}" if not discovery else " | modo descoberta") + ". Ctrl+C para parar.")
    try:
        await dp.start_polling(bot)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[taila] Parado.")
    if serve_proc:
        try:
            serve_proc.terminate()
        except Exception:
            pass