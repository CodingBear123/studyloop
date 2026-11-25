"""Studyloop moved to skills/studyloop/app on 2026-11-25 (the skills are /studyloop and /studyloop-setup now).

This file only forwards, so old shortcuts, the autostart entry and a page restarting after the update keep
working. On the way it moves the old /study and /study-vault skill links or copies to the new names and,
if autostart is on, points it at the new folder.
"""
import os
import sys
from pathlib import Path

NEW = Path(__file__).resolve().parents[2] / "studyloop" / "app"
sys.path.insert(0, str(NEW))
try:
    import updater
    updater.rename_old()
    updater.refresh_copies()
    import launch
    if launch.autostart_file().exists():
        launch.set_autostart(True)
except Exception as e:  # forwarding matters more than tidying up
    print(f"studyloop: couldn't move the old install over ({e})", file=sys.stderr)
target = str(NEW / Path(__file__).name)
if os.name == "nt":
    import subprocess
    sys.exit(subprocess.call([sys.executable, target, *sys.argv[1:]]))
os.execv(sys.executable, [sys.executable, target, *sys.argv[1:]])
