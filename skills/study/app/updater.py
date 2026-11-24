"""Update Studyloop from the page: compare the git checkout with GitHub, pull, refresh copied skills, restart.

Only a git checkout can update itself (the installers clone one when git is there). A copy that was
downloaded as an archive says so and asks for the installer instead. Standard library only.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]  # app -> study -> skills -> repository
SKILLS = ("study", "study-vault")
MARKERS = (".studyloop", ".claude-study-tool")  # left in skill copies by install.ps1 (old name too)
CHECK_EVERY = 3600  # seconds between fetches from GitHub; "check now" skips the wait
_lock = threading.Lock()
_cache = {"at": 0.0, "info": None}


def git(*args, timeout=30):
    """(exit code, output) of a git command in the repository; never asks for a password."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "LC_ALL": "C"}
    try:
        r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=timeout,
                           env=env, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 1, "git took too long (no network?)"
    except OSError as e:
        return 1, str(e)
    return r.returncode, (r.stdout + r.stderr).strip()


def last_line(text):
    lines = [l for l in text.splitlines() if l.strip()]
    return lines[-1] if lines else text


def _check():
    base = {"available": False, "can_update": False, "behind": 0, "changes": [], "reason": ""}
    if not (REPO / ".git").exists():
        return {**base, "reason": "This copy wasn't installed with git, so it can't update itself. "
                                  "Run the installer again to get the newest version."}
    if not shutil.which("git"):
        return {**base, "reason": "git isn't installed, so Studyloop can't update itself."}
    code, out = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if code:
        return {**base, "reason": "This checkout doesn't follow a branch on GitHub."}
    upstream = out
    code, out = git("fetch", "--quiet")
    if code:
        return {**base, "reason": "Couldn't reach GitHub: " + last_line(out)}
    _, behind = git("rev-list", "--count", "HEAD..@{u}")
    _, ahead = git("rev-list", "--count", "@{u}..HEAD")
    _, changes = git("log", "--format=%s", "-n", "8", "HEAD..@{u}")
    _, current = git("rev-parse", "--short", "HEAD")
    _, dirty = git("status", "--porcelain", "--untracked-files=no")
    behind, ahead = int(behind or 0), int(ahead or 0)
    info = {**base, "behind": behind, "ahead": ahead, "upstream": upstream, "current": current,
            "changes": [c for c in changes.splitlines() if c], "local_changes": bool(dirty),
            "available": behind > 0, "can_update": behind > 0}
    if behind and ahead:
        info.update(can_update=False, reason=f"Your copy has {ahead} commit(s) GitHub doesn't have. "
                                             "Merge them by hand (git pull).")
    return info


def status(force=False):
    """What GitHub has that this copy doesn't; cached for CHECK_EVERY seconds."""
    with _lock:
        if force or not _cache["info"] or time.time() - _cache["at"] > CHECK_EVERY:
            _cache.update(at=time.time(), info=_check())
        return _cache["info"]


def refresh_copies(home=None):
    """Windows installs copy the skills instead of linking them: copy them again from the repository."""
    done = []
    for s in SKILLS:
        src, t = REPO / "skills" / s, Path(home or Path.home()) / ".claude" / "skills" / s
        if t.is_symlink() or not t.is_dir() or not src.is_dir() or t.resolve() == src.resolve():
            continue
        if not any((t / m).exists() for m in MARKERS):
            continue  # not ours: leave it alone
        shutil.rmtree(t)
        shutil.copytree(src, t)
        (t / ".studyloop").write_text("Installed by Studyloop; updating replaces this folder.\n", encoding="utf-8")
        done.append(s)
    return done


def apply():
    """git pull --ff-only; ValueError with git's reason if it can't."""
    with _lock:
        if not (REPO / ".git").exists():
            raise ValueError("This copy wasn't installed with git: run the installer again to update.")
        code, out = git("pull", "--ff-only", "--quiet", timeout=180)
        _cache["info"] = None
        if code:
            if "local changes" in out or "would be overwritten" in out:
                raise ValueError("Your own changes to Studyloop's files are in the way. Commit or stash them, "
                                 "then update again.")
            raise ValueError("The update didn't go through: " + last_line(out))
        _, current = git("rev-parse", "--short", "HEAD")
        return {"ok": True, "current": current, "copied": refresh_copies()}


def restart_later(srv, delay=0.4):
    """After the reply has gone out: run this server again with the same arguments, in the same process.

    Not srv.shutdown(): that ends serve_forever, main() returns and the process exits before exec."""
    def go():
        time.sleep(delay)
        srv.server_close()  # free the port first (on Windows execv starts a new process)
        os.execv(sys.executable, [sys.executable, os.path.abspath(sys.argv[0]), *sys.argv[1:]])
    threading.Thread(target=go, daemon=True).start()
