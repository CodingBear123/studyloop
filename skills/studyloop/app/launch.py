#!/usr/bin/env python3
"""Open Studyloop with one click: start the server if it isn't running, then open it in an app window.

The first time (or with --choose) it asks for the folder that holds your StudyVault(s) and remembers
it in the prefs file (~/.config/studyloop/prefs.json). Standard library only.

    python3 launch.py              # open the page
    python3 launch.py ~/Notes      # use this folder from now on
    python3 launch.py --choose     # pick another folder
    python3 launch.py --restart    # restart running pages so they load changed code, then open
    python3 launch.py --tab        # open in a normal browser tab instead of an app window
    python3 launch.py --autostart on|off   # start the server when you log in (it idles in the background)
"""
import json
import os
import shutil
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
TITLE = "Studyloop"
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
                 "If you have no vault yet, ask Claude: /studyloop-setup", error=True)
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


# ---------- app window ----------

def installed_app():
    """The Studyloop app Chrome or Edge made when you clicked Install (macOS), or None."""
    if sys.platform != "darwin":
        return None
    for folder in ("Chrome Apps.localized", "Edge Apps.localized", "Brave Browser Apps.localized"):
        app = Path.home() / "Applications" / folder / "Studyloop.app"
        if app.is_dir():
            return app
    return None


def chromium():
    """A Chrome-family browser that can open a page as an app window: (kind, path) or None."""
    if sys.platform == "darwin":
        for name in ("Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium"):
            for root in (Path("/Applications"), Path.home() / "Applications"):
                if (root / f"{name}.app").is_dir():
                    return "mac", name
        return None
    if os.name == "nt":
        roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        rel = [r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe",
               r"BraveSoftware\Brave-Browser\Application\brave.exe"]
        for r in rel:
            for root in filter(None, roots):
                exe = Path(root) / r
                if exe.is_file():
                    return "exe", str(exe)
        return None
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"):
        exe = shutil.which(name)
        if exe:
            return "exe", exe
    return None


def open_window(url, tab=False):
    """The page in its own window (installed app, or Chrome/Edge --app); a browser tab as the fallback."""
    if not tab:
        try:
            app = installed_app()
            if app and url.startswith("http://127.0.0.1:8765/"):
                subprocess.Popen(["open", str(app)])
                return
            found = chromium()
            if found and found[0] == "mac":
                subprocess.Popen(["open", "-na", found[1], "--args", f"--app={url}"])
                return
            if found:
                kw = {"creationflags": 0x00000008} if os.name == "nt" else {"start_new_session": True}
                subprocess.Popen([found[1], f"--app={url}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
                return
        except OSError:
            pass
    webbrowser.open(url)


# ---------- start at login ----------

AGENT = Path.home() / "Library" / "LaunchAgents" / "com.studyloop.server.plist"
STARTUP = Path(os.environ.get("APPDATA") or Path.home()) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Studyloop.vbs"
DESKTOP = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart" / "studyloop.desktop"


def autostart_file():
    return AGENT if sys.platform == "darwin" else STARTUP if os.name == "nt" else DESKTOP


def set_autostart(on):
    """Start the server (no window) when you log in, or stop doing that. Returns the file it wrote or removed."""
    path = autostart_file()
    if not on:
        if path.exists():
            path.unlink()
        return path
    py, me = sys.executable, str(HERE / "launch.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        log = server.PREFS_FILE.parent / "autostart.log"
        from xml.sax.saxutils import escape as x
        path.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.studyloop.server</string>
  <key>ProgramArguments</key><array><string>{x(py)}</string><string>{x(me)}</string><string>--no-browser</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{x(str(log))}</string>
  <key>StandardErrorPath</key><string>{x(str(log))}</string>
</dict></plist>
""", encoding="utf-8")
    elif os.name == "nt":
        pyw = Path(py).with_name("pythonw.exe")
        exe = str(pyw if pyw.is_file() else py)
        path.write_text(f'CreateObject("WScript.Shell").Run """{exe}"" ""{me}"" --no-browser", 0, False\r\n',
                        encoding="utf-8")
    else:
        path.write_text(f"[Desktop Entry]\nType=Application\nName=Studyloop\nExec=\"{py}\" \"{me}\" --no-browser\n"
                        "X-GNOME-Autostart-enabled=true\nNoDisplay=true\n", encoding="utf-8")
    return path


def restart_all():
    """Ask every running study page to restart itself (it keeps its folder and port)."""
    done = []
    for port in PORTS:
        if running(port) is None:
            continue
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/restart", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:
            continue  # an old version without /api/restart: leave it running
        done.append(port)
    for port in done:
        time.sleep(0.6)
        for _ in range(40):
            if running(port) is not None:
                break
            time.sleep(0.25)
        print(f"restarted the page on port {port}")
    return done


def main():
    if "--autostart" in sys.argv:
        i = sys.argv.index("--autostart")
        mode = sys.argv[i + 1] if i + 1 < len(sys.argv) else "status"
        del sys.argv[i:i + 2]
        if mode not in ("on", "off", "status"):
            raise SystemExit("use --autostart on, off or status")
        if mode == "status":
            print(f"autostart is {'on' if autostart_file().exists() else 'off'} ({autostart_file()})")
            return
        path = set_autostart(mode == "on")
        print(f"autostart {mode}: {path}")
        if mode == "off":
            return
        sys.argv.append("--no-browser")  # make sure a server runs now too
    if "--restart" in sys.argv:
        restart_all()

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    folder, vaults = pick_vaults(args[0] if args else None, "--choose" in sys.argv)
    port = start(folder, vaults)
    url = f"http://127.0.0.1:{port}/"
    print(f"Study page: {url}")
    if "--no-browser" not in sys.argv:
        open_window(url, tab="--tab" in sys.argv)


if __name__ == "__main__":
    main()
