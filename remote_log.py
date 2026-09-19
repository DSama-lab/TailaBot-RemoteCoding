"""remote_log.py — log persistente do RemoteCoding (TailaBot)

Cada tarefa executada via Telegram (texto, botao, arquivo ou comando local)
fica registrada em REMOTE_LOG.md, nesta mesma pasta. Assim, ao chegar no PC,
basta pedir ao opencode para ler este arquivo e resumir onde paramos.

CLI (no PC):
  python remote_log.py             -> resumo dos ultimos 10 registros
  python remote_log.py last 5      -> ultimos 5 registros completos
  python remote_log.py full        -> arquivo inteiro (pode ser grande)
  python remote_log.py grep TERMO  -> registros que contenham TERMO
"""

import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = Path(os.getenv("REMOTE_LOG_FILE", str(BASE_DIR / "REMOTE_LOG.md")))
MAX_TEXT = 1500
MAX_PROMPT = 500


def _now():
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _trunc(value, limit):
    value = value if value is not None else ""
    value = str(value).strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "…"


def append(origem, prompt, ok, session_id=None, text="", error=None, extra=None):
    """Appenda um registro de tarefa no REMOTE_LOG.md."""
    prefix = "OK" if ok else "FALHA"
    lines = [
        f"## [{prefix}] {_now()} — {origem}",
        f"- **Prompt:** {_trunc(prompt, MAX_PROMPT)}",
    ]
    if session_id:
        lines.append(f"- **Sessão opencode:** `{session_id}`")
    if extra:
        lines.append("- **Extra:** " + _trunc(str(extra), MAX_PROMPT))
    if error:
        lines.append(f"- **Erro:** {_trunc(str(error), 500)}")
    body = _trunc(text, MAX_TEXT) if text else "(sem resposta)"
    lines.append(f"- **Resposta:** {body}")
    lines.append("")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return LOG_FILE


def entries():
    """Itera sobre os registros do log do mais antigo para o mais novo."""
    if not LOG_FILE.exists():
        return
    current = []
    for raw in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if raw.startswith("## "):
            if current:
                yield "\n".join(current)
            current = [raw]
        elif current:
            current.append(raw)
    if current:
        yield "\n".join(current)


def last(n=10):
    return list(entries())[-n:]


def _match(entry, term):
    return term.lower() in entry.lower()


def subset(term, n=50):
    return [e for e in entries() if _match(e, term)][-n:]


def main():
    args = sys.argv[1:]
    if not args:
        for e in last(10):
            print(e)
            print("---")
        return
    cmd = args[0].lower()
    if cmd == "last":
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        for e in last(n):
            print(e)
            print("---")
    elif cmd == "full":
        if LOG_FILE.exists():
            print(LOG_FILE.read_text(encoding="utf-8"))
        else:
            print("log ainda vazio")
    elif cmd == "grep" and len(args) > 1:
        for e in subset(args[1]):
            print(e)
            print("---")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()