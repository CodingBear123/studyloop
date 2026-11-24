#!/bin/sh
# Studyloop installer for macOS and Linux. Safe to run again: it updates what is there.
#
#   From a downloaded copy:  sh install.sh
#   Straight from GitHub:    curl -fsSL https://raw.githubusercontent.com/CodingBear123/studyloop/main/install.sh | sh
#
# What it does: checks Python, gets the tool (into ~/.studyloop unless run from a copy),
# links the /study and /study-vault skills into ~/.claude/skills, adds the "Studyloop" app and the
# `studyloop` command, and checks for Claude Code and pdftotext.
set -e

REPO="CodingBear123/studyloop"
DEST="${STUDYLOOP_HOME:-$HOME/.studyloop}"
SKILLS="$HOME/.claude/skills"
BIN="$HOME/.local/bin"

bold() { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
ask() {  # ask "Question?" -> 0 for yes (works when the script is piped into sh)
  if (: < /dev/tty) 2>/dev/null; then printf '  %s [Y/n] ' "$1"; read -r a < /dev/tty || a=n; else a=n; fi
  case "$a" in [nN]*) return 1 ;; *) return 0 ;; esac
}

bold "Studyloop"

# 1. Python 3.9+ (on a Mac without it, python3 is a stub that offers to install the developer tools)
bold "1/5 Python"
if python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
  PY="$(command -v python3)"
  ok "Python $(python3 -c 'import platform; print(platform.python_version())')"
else
  if [ "$(uname)" = "Darwin" ]; then
    warn "Python isn't installed yet. A window will ask to install Apple's command line developer tools:"
    warn "click Install, wait until it is done, then run this installer again."
    xcode-select --install >/dev/null 2>&1 || true
  else
    warn "Install Python 3.9 or newer (e.g. sudo apt install python3), then run this installer again."
  fi
  exit 1
fi

# 2. The tool itself: use this copy if the script runs from one, else download or update ~/.studyloop
bold "2/5 Studyloop"
HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")"
OLD="$HOME/.claude-study-tool"  # where it lived before the rename to Studyloop
if [ -z "$STUDYLOOP_HOME" ] && [ -d "$OLD" ] && [ ! -e "$DEST" ]; then
  mv "$OLD" "$DEST" && ok "moved $OLD to $DEST"
fi
if [ -n "$HERE" ] && [ -f "$HERE/skills/study/app/server.py" ]; then
  SRC="$HERE"
  ok "using this copy: $SRC"
elif [ -d "$DEST/.git" ] && git --version >/dev/null 2>&1; then
  git -C "$DEST" pull --ff-only --quiet && ok "updated $DEST" || warn "couldn't update $DEST, keeping the version there"
  SRC="$DEST"
elif git --version >/dev/null 2>&1 && git clone --quiet "https://github.com/$REPO.git" "$DEST.new" 2>/dev/null; then
  rm -rf "$DEST"; mv "$DEST.new" "$DEST"; SRC="$DEST"
  ok "downloaded to $DEST"
else
  rm -rf "$DEST.new"; mkdir -p "$DEST.new"
  if curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/main" | tar -xz -C "$DEST.new" --strip-components 1; then
    rm -rf "$DEST"; mv "$DEST.new" "$DEST"; SRC="$DEST"
    ok "downloaded to $DEST"
  else
    rm -rf "$DEST.new"
    warn "Couldn't download $REPO. If the repository is private, download it as a ZIP from GitHub,"
    warn "unpack it, and run install.sh from inside that folder."
    exit 1
  fi
fi
APP="$SRC/skills/study/app"

# 3. Skills for Claude Code (a link, so updating the tool updates the skills)
bold "3/5 /study and /study-vault for Claude"
mkdir -p "$SKILLS"
for s in study study-vault; do
  if [ -e "$SKILLS/$s" ] && [ ! -L "$SKILLS/$s" ]; then
    mv "$SKILLS/$s" "$SKILLS/$s.backup-$(date +%Y%m%d%H%M%S)"
    warn "moved your old $s skill folder aside ($s.backup-…)"
  fi
  ln -sfn "$SRC/skills/$s" "$SKILLS/$s"
  ok "/$s"
done

# 4. One-click start: an app (Mac) or menu entry (Linux), plus the studyloop command
bold "4/5 The Studyloop app"
mkdir -p "$BIN"
# the names from before the rename (Claude Study)
rm -f "$BIN/claude-study" "$HOME/.local/share/applications/claude-study.desktop"
rm -rf "$HOME/Applications/Claude Study.app"
[ -L "$HOME/Desktop/Claude Study" ] && rm -f "$HOME/Desktop/Claude Study"
cat > "$BIN/studyloop" <<EOF
#!/bin/sh
exec "$PY" "$APP/launch.py" "\$@"
EOF
chmod +x "$BIN/studyloop"
ok "command: studyloop"
case ":$PATH:" in *":$BIN:"*) ;; *) warn "$BIN isn't on your PATH; the app below works anyway" ;; esac
if [ "$(uname)" = "Darwin" ]; then
  mkdir -p "$HOME/Applications"
  TARGET="$HOME/Applications/Studyloop.app"
  rm -rf "$TARGET"
  osacompile -o "$TARGET" -e "do shell script quoted form of \"$PY\" & \" \" & quoted form of \"$APP/launch.py\" & \" >/dev/null 2>&1; true\"" >/dev/null 2>&1
  ok "app: ~/Applications/Studyloop.app (also in Spotlight and Launchpad)"
  if ask "Put a Studyloop shortcut on your Desktop too?"; then
    ln -sfn "$TARGET" "$HOME/Desktop/Studyloop" && ok "Desktop shortcut"
  fi
else
  mkdir -p "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/applications/studyloop.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Studyloop
Comment=Open the study page
Exec="$PY" "$APP/launch.py"
Terminal=false
Categories=Education;
EOF
  ok "menu entry: Studyloop"
fi

# 5. What the skills need besides Python
bold "5/5 Checks"
if command -v claude >/dev/null 2>&1 || [ -x "$HOME/.local/bin/claude" ]; then
  ok "Claude Code"
else
  warn "Claude Code isn't installed. /study and /study-vault run inside it, and the page uses it for"
  warn "\"Check with Claude\" and \"Ask Claude\"."
  if ask "Install Claude Code now (official installer from claude.ai)?"; then
    curl -fsSL https://claude.ai/install.sh | bash && ok "Claude Code installed; run 'claude' once to sign in"
  else
    warn "Later: https://claude.com/claude-code"
  fi
fi
if command -v pdftotext >/dev/null 2>&1; then
  ok "pdftotext (reads PDF slides)"
elif command -v brew >/dev/null 2>&1 && ask "Install pdftotext with Homebrew (to read PDF slides)?"; then
  brew install poppler >/dev/null && ok "pdftotext"
else
  warn "pdftotext is missing: /study-vault reads PDFs better with it (Mac: brew install poppler)"
fi

bold "Done."
echo "  Make study notes: open Claude in your course folder and type /study-vault"
echo "  Study:            type /study, or open the Studyloop app"
