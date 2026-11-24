#!/usr/bin/env python3
"""Open the study page with one click: start the server if it isn't running, then open the browser.

The first time (or with --choose) it asks for the folder that holds your StudyVault(s) and remembers
it in the prefs file (~/.config/claude-study/prefs.json). Standard library only.

    python3 launch.py              # open the page
    python3 launch.py ~/Notes      # use this folder from now on
    python3 launch.py --choose     # pick another folder
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402
import studyvault as sv  # noqa: E402

PORTS = range(8765, 8776)
TITLE = "Claude Study"
# A double-clicked app gets a short PATH; add the places Claude Code and Homebrew install to,
# so the server finds `claude` for checks and questions.
EXTRA_PATH = [Path.home() / ".local" / "bin", Path.home() / ".claude" / "local", Path("/opt/homebrew/bin"),
              Path("/usr/local/bin"), Path.home() / "AppData" / "Roaming" / "npm"]


def tell(msg, error=False):
    """Show a message even when there is no terminal (double-clicked app)."""
    print(msg, file=sys.stderr if error else sys.stdout)
    if sys.stdout and sys.stdout.isatty():
        return
    try:
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e", f"display dialog {json.dumps(msg)} with title {json.dumps(TITLE)} "
                            f"buttons {{\"OK\"}} default button 1 with icon {'stop' if error else 'note'}"],
                           capture_output=True)
        elif os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, TITLE, 0x10 if error else 0x40)
    except Exception:
        pass


def choose_folder():
    """A native folder picker; None if cancelled."""
    prompt = ("Choose your course folder. Have several courses? Choose the folder they are all in "
              "(e.g. your semester folder): every StudyVault inside it shows up on the page.")
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["osascript", "-e", f"POSIX path of (choose folder with prompt {json.dumps(prompt)})"],
                               capture_output=True, text=True)
            return r.stdout.strip() or None
        if os.name == "nt":
            ps = ("Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; "
                  f"$d.Description = {json.dumps(prompt)}; if ($d.ShowDialog() -eq 'OK') {{ $d.SelectedPath }}")
            r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True,
                               creationflags=0x08000000)
            return r.stdout.strip() or None
        r = subprocess.run(["zenity", "--file-selection", "--directory", "--title", prompt], capture_output=True, text=True)
        return r.stdout.strip() or None
    except FileNotFoundError:
        pass
    if sys.stdin and sys.stdin.isatty():
        return input(prompt + ": ").strip() or None
    return None


def save(**kv):
    prefs = {**server.raw_prefs(), **kv}
    server.PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    server.PREFS_FILE.write_text(json.dumps(prefs, indent=2) + "\n", encoding="utf-8")


def vaults_in(folder):
    return [str(v) for v in sv.find_vaults(folder)] if folder and Path(folder).expanduser().is_dir() else []


def pick_vaults(arg, force):
    """(folder, vault paths), asking for a folder when there is none or it holds no vault."""
    prefs = server.raw_prefs()
    folder, vaults = prefs.get("folder"), prefs.get("vaults") or []
    if arg:
        folder, vaults = str(Path(arg).expanduser().resolve()), None
    elif force:
        folder, vaults = None, None
    if folder and vaults and all(Path(v).is_dir() for v in vaults):
        return folder, vaults
    if folder:
        vaults = vaults_in(folder)  # stored list is stale, or a new folder: look again
    while not vaults:
        if folder:
            tell(f"There is no StudyVault in\n{folder}\n\nPick the folder your course notes are in. "
                 "If you have no vault yet, ask Claude: /study-vault", error=True)
        folder = choose_folder()
        if not folder:
            sys.exit(1)
        folder = str(Path(folder).expanduser().resolve())
        vaults = vaults_in(folder)
    save(folder=folder, vaults=vaults)
    return folder, vaults


def running(port):
    """Vault paths served on this port, or None if nothing (or something else) answers there."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vaults", timeout=1.5) as r:
            data = json.load(r)
        return {str(Path(v["path"]).resolve()) for v in data}
    except Exception:
        return None


def port_free(port):
    import socket
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def start(folder, vaults):
    """Reuse a server that already serves these vaults, else start one on the first free port."""
    want = {str(Path(v).resolve()) for v in vaults}
    for port in PORTS:
        have = running(port)
        if have is not None and want <= have:
            return port
    port = next((p for p in PORTS if port_free(p)), None)
    if port is None:
        raise SystemExit(tell(f"Ports {PORTS.start}-{PORTS.stop - 1} are all busy.", error=True) or 1)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([env.get("PATH", "")] + [str(p) for p in EXTRA_PATH if p.is_dir()])
    log = server.PREFS_FILE.parent / "server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(HERE / "server.py"), "--root", folder, "--port", str(port)]
    for v in vaults:
        cmd += ["--vault", v]
    kw = {"creationflags": 0x00000008 | 0x00000200 | 0x08000000} if os.name == "nt" else {"start_new_session": True}
    with open(log, "a", encoding="utf-8") as out:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=out, env=env, close_fds=True, **kw)
    for _ in range(60):
        if running(port) is not None:
            return port
        if proc.poll() is not None:
            break
        time.sleep(0.25)
    tell(f"The study page didn't start. Details are in\n{log}", error=True)
    sys.exit(1)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    folder, vaults = pick_vaults(args[0] if args else None, "--choose" in sys.argv)
    port = start(folder, vaults)
    url = f"http://127.0.0.1:{port}/"
    print(f"Study page: {url}")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
