"""rotina.py - rotina local de avisos (registro de atividade do dia).

Nao depende de servidor externo alem do proprio bot do Telegram.
Funciona em segundo plano: confere registros de auditoria e portas locais
a cada ciclo e avisa (via canal do bot) quando algo muda.
"""

import datetime
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
SNAP = BASE / "rotina.snap.json"
LOG = BASE / "rotina.log"
CICLO = 60


def _env(key):
    try:
        for line in (BASE / ".env").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


TOKEN = _env("BOT_TOKEN")
CHAT = _env("OWNER_CHAT_ID")


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("%s | %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def enviar(texto):
    if not TOKEN or not CHAT:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": CHAT, "text": texto}).encode()
        req = urllib.request.Request(
            "https://api.telegram.org/bot%s/sendMessage" % TOKEN, data=data
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        return bool(j.get("ok"))
    except Exception as e:
        log("envio: %s" % e)
        return False


def _carregar():
    try:
        return json.loads(SNAP.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _salvar(d):
    try:
        SNAP.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _publicas(portas):
    res = set()
    for p in portas:
        if p.startswith("0.0.0.0:") or p.startswith("[::]:"):
            res.add(p)
    return res


def _ouvidas():
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
    except Exception:
        return set()
    res = set()
    for line in out.splitlines():
        line = line.strip()
        if "LISTENING" not in line:
            continue
        m = re.match(r"TCP\s+(\S+)\s+\S+\s+LISTENING", line)
        if not m:
            continue
        a = m.group(1)
        if a.startswith(("127.", "[::1]")):
            continue
        res.add(a)
    return res


def _eventos(ultimo):
    """Retorna (ultimo_record, linhas) lendo auditoria Windows (exige elevacao)."""
    try:
        script = (
            "$e=Get-WinEvent -FilterHashtable @{LogName='Security';Id=4624,4625,4720,4728,4732,4756} "
            "-ErrorAction SilentlyContinue | Where-Object {$_.RecordId -gt %s} | Select-Object -First 50; "
            "$e | ForEach-Object {"
            "$t=($_.Message -replace '\\s+',' ');"
            "[pscustomobject]@{r=$_.RecordId;t=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm');id=$_.Id;"
            "m=$t.Substring(0,[Math]::Min(160,$t.Length))} } | ConvertTo-Json -Compress"
        ) % int(ultimo)
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=40,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        raw = out.stdout.strip()
        if not raw or raw in ("[]", "null"):
            return ultimo, None
        data = json.loads(raw)
        if not isinstance(data, list):
            data = [data]
        maxrec = int(ultimo)
        linhas = []
        for it in data:
            r = int(it.get("r") or 0)
            if r > maxrec:
                maxrec = r
            linhas.append("%s | evento %s | %s" % (it.get("t", ""), it.get("id", ""), it.get("m", "")))
        return maxrec, linhas
    except Exception as e:
        log("eventos indisponiveis: %s" % e)
        return ultimo, None


def main():
    snap = _carregar()
    primeiro = not snap
    last_evento = int(snap.get("ultimo_evento") or 0)
    base = set(snap.get("ouvidas") or [])
    while True:
        agora = datetime.datetime.now().strftime("%d/%m %H:%M")
        avisos = []

        atuais = _publicas(_ouvidas())
        if base:
            novas = sorted(p for p in atuais if p not in base)
            sumidas = sorted(p for p in base if p not in atuais)
            if novas:
                avisos.append("nova porta publica: " + "; ".join(novas))
            if sumidas:
                avisos.append("porta publica fechou: " + "; ".join(sumidas))
        base = atuais

        last_evento, linhas = _eventos(last_evento)
        if linhas:
            avisos.extend(linhas[-12:])

        if avisos:
            log("avisos: %d" % len(avisos))
            enviar("Aviso de rotina (%s):\n- %s" % (agora, "\n- ".join(avisos)))
        elif primeiro:
            log("primeira execucao")
            enviar("Rotina ativa. Canal de avisos disponivel.")
            primeiro = False

        _salvar({"ultimo_evento": last_evento, "ouvidas": sorted(base)})
        for _ in range(CICLO):
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("parado")
        pass