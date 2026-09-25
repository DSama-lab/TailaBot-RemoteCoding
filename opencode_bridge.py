import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

_tmp = None
_windows = sys.platform == "win32"


def _proc_kwargs(stdout_target):
    kwargs = {
        "stdout": stdout_target,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if _windows:
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _tmpfile(prefix, suffix=".log"):
    global _tmp
    if _tmp is None:
        _tmp = os.path.join(tempfile.gettempdir(), "tailabot")
        os.makedirs(_tmp, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=_tmp)
    os.close(fd)
    return path


def _opencode():
    return shutil.which("opencode") or "opencode"


def _kill_tree(pid):
    if _windows:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        try:
            os.kill(pid, 9)
        except Exception:
            pass


def server_is_up(base_url, timeout=2.0):
    try:
        urllib.request.urlopen(base_url, timeout=timeout)
        return True
    except Exception:
        return False


def start_server(port, print_logs=False):
    cmd = [_opencode(), "serve", "--port", str(port)]
    if print_logs:
        cmd.append("--print-logs")
    log = _tmpfile(f"serve-{port}-")
    handle = open(log, "ab")
    proc = subprocess.Popen(cmd, **_proc_kwargs(handle))
    proc._log_file = handle
    proc._log_path = log
    return proc


def _parse_run_output(raw):
    parts = []
    session_id = None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        etype = ev.get("type", "")
        if not session_id:
            sid = ev.get("sessionID") or ev.get("session", {})
            if isinstance(sid, str) and sid:
                session_id = sid
            elif isinstance(sid, dict) and sid.get("id"):
                session_id = sid["id"]
            else:
                session_id = ev.get("value") or ev.get("sessionId")
        if etype == "text":
            p = ev.get("part") or {}
            if p.get("text") and p.get("type") not in ("tool", "tool_use"):
                parts.append(p["text"])
        elif etype == "message.part.updated":
            p = ev.get("part", {})
            if p.get("type") == "text" and p.get("text"):
                parts.append(p["text"])
        elif etype == "message.updated" and ev.get("message", {}).get("role") == "assistant":
            sid = ev.get("message", {}).get("sessionID")
            if sid:
                session_id = sid
        elif etype == "error":
            err = ev.get("error", {})
            if isinstance(err, dict):
                msg = err.get("data", {}).get("message") or err.get("message")
                if str(msg).strip() == "OK":
                    msg = "OK"
            elif isinstance(err, str):
                msg = err
            if isinstance(msg, str) and not parts:
                pass
    text = "".join(parts).strip()
    if not text:
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                text = line.strip()
                if text:
                    break
    return text, session_id


def run_task(prompt, base_url, work_dir, session_id=None, files=None, timeout=600, on_progress=None, model=None):
    # NOTA (2026-09-19): sem "--attach". O opencode 1.18.x, quando usa `run --attach` num
    # servidor remoto, emite só `step_start` e encerra sem repassar os eventos de texto ao CLI.
    # No modo direto (`opencode run --format json --dir ...`) os eventos `type:"text"` chegam
    # normalmente e o storage/sessões são os mesmos (continuidade via --session funciona).
    cmd = [_opencode(), "run", "--format", "json"]
    if model:
        cmd += ["--model", model]
    if work_dir:
        cmd += ["--dir", work_dir]
    if session_id:
        cmd += ["--session", session_id]
    for f in files or []:
        cmd += ["--file", f]
    cmd += [prompt]

    log = _tmpfile("run-")
    handle = open(log, "ab")
    last_progress = ""
    try:
        proc = subprocess.Popen(cmd, **_proc_kwargs(handle))
        deadline = time.monotonic() + timeout
        timed_out = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            if on_progress:
                emitted = _emit_progress(log, last_progress, on_progress)
                if emitted is not None:
                    last_progress = emitted
            time.sleep(0.5)
        else:
            timed_out = True
            _kill_tree(proc.pid)
            proc.wait()
    finally:
        handle.close()

    with open(log, "rb") as fh:
        raw = fh.read().decode("utf-8", errors="replace")
    try:
        os.remove(log)
    except Exception:
        pass

    if timed_out:
        return {"ok": False, "text": "⏰ tempo esgotado", "session_id": None, "raw": raw[-3000:]}

    text, sid = _parse_run_output(raw)
    if not text and proc.returncode != 0:
        text = raw.strip()[-2000:] or f"exit {proc.returncode}"
    if not text:
        text = "(sem resposta de texto)"
    return {"ok": proc.returncode == 0, "text": text, "session_id": sid, "raw": raw}


def _emit_progress(log_path, last_progress, on_progress):
    try:
        with open(log_path, "rb") as fh:
            raw = fh.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    marker = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        etype = ev.get("type", "")
        part = ev.get("part") or {}
        pt = part.get("type")
        if etype == "text":
            if pt in ("text", None) and part.get("text"):
                marker = part["text"]
        elif etype == "tool_use" or (etype == "message.part.updated" and pt == "tool"):
            tool = part.get("tool") or "ferramenta"
            state = part.get("state")
            status = state.get("status") if isinstance(state, dict) else None
            if status in ("running", "completed", None):
                marker = f"[ferramenta] {tool}"
        elif etype == "error":
            marker = "erro na tarefa"
    if marker and marker != last_progress:
        on_progress(marker[-400:])
        return marker
    return last_progress


def wait_for_server(base_url, tries=30, sleep=1.0):
    for _ in range(tries):
        if server_is_up(base_url):
            return True
        time.sleep(sleep)
    return False


def run_local(cmd, cwd, timeout=600):
    log = _tmpfile("local-")
    handle = open(log, "ab")
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, **_proc_kwargs(handle))
        deadline = time.monotonic() + timeout
        timed_out = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        else:
            timed_out = True
            _kill_tree(proc.pid)
            proc.wait()
    finally:
        handle.close()
    with open(log, "rb") as fh:
        raw = fh.read().decode("utf-8", errors="replace")
    try:
        os.remove(log)
    except Exception:
        pass
    if timed_out:
        return {"ok": False, "text": "⏰ tempo esgotado", "raw": raw[-3000:]}
    text = raw.strip()[-3000:]
    if not text:
        text = f"(sem saída, exit {proc.returncode})"
    return {"ok": proc.returncode == 0, "text": text, "raw": raw}


def read_server_log(proc, tail=3000):
    try:
        with open(proc._log_path, "rb") as fh:
            return fh.read().decode("utf-8", errors="replace")[-tail:]
    except Exception:
        return ""


def zip_folder(folder_path, dest_zip):
    folder_path = os.path.normpath(folder_path)
    dest_zip = os.path.normpath(dest_zip)
    shutil.make_archive(
        os.path.splitext(dest_zip)[0],
        "zip",
        root_dir=os.path.dirname(folder_path),
        base_dir=os.path.basename(folder_path),
    )
    return dest_zip if os.path.exists(dest_zip) else dest_zip + ".zip"