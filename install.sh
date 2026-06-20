#!/data/data/com.termux/files/usr/bin/bash
# MINXG install.sh - one-line bootstrap for any platform.
#
# USAGE:
# Local: bash install.sh # clone-mode auto-skip
# Remote: curl -fsSL https://REPO/install.sh | bash # auto clone to ~/.minxg-src
# Custom: REPO_URL=https://github.com/you/minxg.git curl -fsSL ... | bash
# Branch: MINXG_BRANCH=dev bash install.sh
# Dir: MINXG_DIR=/opt/minxg bash install.sh
#
# Edit REPO_URL_DEFAULT below to point at the upstream you fork from.
set -e

# ── : --help / -h ─────────────────────────────────
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
 cat <<'USAGE'
MINXG install.sh — bootstrap a fresh machine with one command.

USAGE:
 bash install.sh # local repo mode (auto-detect)
 curl -fsSL <host>/install.sh | bash # clone defaults
 curl -fsSL <host>/install.sh | bash -s -- ARG... # pass extra args

ARGUMENTS (positional, evaluated in order; env vars win when set):
 $1 repo URL (env: REPO_URL) default: see header
 $2 install dir (env: MINXG_DIR) default: $HOME/.minxg-src
 $3 git branch (env: MINXG_BRANCH) default: (default branch)

OPTIONS:
 --help, -h show this message and exit

ENVIRONMENT:
 REPO_URL override the default clone URL
 MINXG_DIR change the clone destination (avoids an existing dir)
 MINXG_BRANCH pin a branch / tag to clone
 PYTHON python interpreter to use (default: python3)

EXAMPLES:
 # fresh machine, one line:
 curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh | bash

 # fork:
 REPO_URL=https://github.com/you/minxg.git bash install.sh

 # already cloned:
 cd minxg && bash install.sh

The script is self-contained: no external config, no env required.
USAGE
 
# ── Completion cheatsheet ────────────────────────────
cat <<'CHEATSHEET'
+--------------------------------------------------------------------+
| MINXG - installed |
+--------------------------------------------------------------------+
| |
| minxg start the TUI chat |
| minxg setup run the setup wizard |
| minxg config show current configuration |
| minxg status runtime status |
| minxg tools list available tools |
| minxg ext available list built-in optional extensions |
| minxg ext add minxg-adb install ADB tools (opt-in) |
| minxg ext add minxg-root install ROOT tools (opt-in) |
| minxg gateway start start the API gateway |
| minxg doctor self-check |
| minxg --version show version |
| |
| Try now: |
| $ minxg --version |
| $ minxg config |
| $ minxg |
+--------------------------------------------------------------------+
CHEATSHEET
exit 0
fi

# ── — URL ───────────────────
# Priority: $1 > $REPO_URL > . ($1="") env.
REPO_URL_DEFAULT="https://github.com/pineapple-ooo/MINXG-Beta.git"
REPO_URL="${1:-${REPO_URL:-$REPO_URL_DEFAULT}}"
INSTALL_DIR="${MINXG_DIR:-${2:-$HOME/.minxg-src}}"
CLONE_BRANCH="${MINXG_BRANCH:-${3:-}}"
# ───────────────────────────────────────────────────────

echo "════════════════════════════════════════"
echo " MINXG v0.11.0 "
echo "════════════════════════════════════════"
echo ""

# ── vs ────────────────────────────
# : $0 BASH_SOURCE[0] "bash" "/dev/stdin" (),
# dirname , $SCRIPT_DIR , git clone。
# :
# 1. BASH_SOURCE[0] → 
# 2. -t 0 (stdin=tty) → 
# 3. → 
LOCAL_MODE=true
BS0="${BASH_SOURCE[0]:-}"
# 1) Script file present -> local mode
if [ -n "$BS0" ] && [ -f "$BS0" ]; then
 LOCAL_MODE=true
# 2) stdin is a TTY -> local mode
elif [ -t 0 ]; then
 LOCAL_MODE=true
# 3) Anything else (curl|bash / bash < script / heredoc) -> piped mode
else
 LOCAL_MODE=false
fi

if [ "$LOCAL_MODE" = true ]; then
 SCRIPT_DIR="$(cd "$(dirname "$BS0")" && pwd)"
 echo " mode: local (SCRIPT_DIR = $SCRIPT_DIR)"
else
 echo " mode: remote one-line install (curl | bash)"
 echo " repo: $REPO_URL"
 echo " dir: $INSTALL_DIR"
 echo ""

 # git + curl . .
 if ! command -v git >/dev/null 2>&1; then
 printf " \033[31m✗\033[0m piped mode requires git to clone the repo\n"
 case "$(uname -s)" in
 Linux)
 if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ]; then
 echo " install: pkg install git"
 else
 echo " install: sudo apt install git"
 fi
 ;;
 Darwin) echo " install: brew install git (or xcode-select --install)" ;;
 MINGW*|MSYS*|CYGWIN*) echo " download: https://git-scm.com/download/win" ;;
 esac
 exit 1
 fi
 if ! command -v curl >/dev/null 2>&1; then
 printf " \033[31m✗\033[0m piped mode requires curl\n"
 echo " (You ran this script via curl - how is curl not on PATH?)"
 exit 1
 fi

 mkdir -p "$INSTALL_DIR"
 if [ -d "$INSTALL_DIR/.git" ]; then
 echo " [0/8] updating existing repo: $INSTALL_DIR"
 if [ -n "$CLONE_BRANCH" ]; then
 git -C "$INSTALL_DIR" fetch --depth 1 origin "$CLONE_BRANCH" >/dev/null 2>&1 || true
 git -C "$INSTALL_DIR" checkout "$CLONE_BRANCH" >/dev/null 2>&1 || true
 else
 git -C "$INSTALL_DIR" pull --ff-only 2>&1 | tail -3 || true
 fi
 else
 echo " [0/8] cloning repo to: $INSTALL_DIR"
 CLONE_ARGS=(--depth 1)
 if [ -n "$CLONE_BRANCH" ]; then
 CLONE_ARGS+=(--branch "$CLONE_BRANCH")
 fi
 # repo git () — 
 if [ -d "$INSTALL_DIR" ] && [ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
 printf " \033[31m✗\033[0m $INSTALL_DIR exists, non-empty, and is not a git repo\n"
 echo " pin a clean dir: MINXG_DIR=/path/to/clean/dir"
 exit 1
 fi
 if ! git clone "${CLONE_ARGS[@]}" "$REPO_URL" "$INSTALL_DIR"; then
 printf " \033[31m✗\033[0m clone failed: $REPO_URL\n"
 echo " check network / repo URL / permissions"
 exit 1
 fi
 fi
 printf " \033[32m✓\033[0m repo ready\n"
 echo ""
 SCRIPT_DIR="$INSTALL_DIR"
fi

# ── ────────────────────────────────────────────
detect_platform() {
 case "$(uname -s)" in
 Linux)
 if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ]; then
 echo "android"
 else
 echo "linux"
 fi
 ;;
 Darwin) echo "macos" ;;
 MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
 *) echo "unknown" ;;
 esac
}

PLATFORM=$(detect_platform)
echo " platform: $PLATFORM"
echo ""

# ── ────────────────────────────────────────────
echo "[1/6] checking python..."
python3 --version || {
 echo ""
 printf " \033[31m✗\033[0m python 3.10+ required\n"
 case "$PLATFORM" in
 android)
 echo " install: pkg install python"
 ;;
 linux)
 echo " install: sudo apt install python3 python3-pip"
 ;;
 macos)
 echo " install: brew install python@3"
 ;;
 esac
 exit 1
}
echo " ✅ Python: $(python3 --version)"

echo "[2/6] installing python dependencies..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
 pip install -q --disable-pip-version-check -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || {
 printf " \033[33m⚠\033[0m some dependencies failed; continuing\n"
 }
else
 pip install -q --disable-pip-version-check pip --upgrade 2>/dev/null || true
fi
printf " \033[32m✓\033[0m dependencies installed\n"

# ── console_script ( `minxg` ) ────────
# Why: pyproject.toml defines `[project.scripts] minxg = "multiligua_cli.main:main"`.
# Without this step, the `minxg` command is not on PATH anywhere, so the user has to
# type `python3 -m multiligua_cli` after every install. `pip install -e .` reads the
# entry-points table and drops a launcher in $(python -m site --user-base)/bin
# (or termux-prefix/usr/bin) so `minxg --help` works from any directory.
echo "[3/6] registering global command (pip install -e .)..."
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
 # Prefer the python that ships the deps we just installed.
 PY_FOR_INSTALL="${PYTHON:-python3}"
 if "$PY_FOR_INSTALL" -m pip install -q --disable-pip-version-check -e "$SCRIPT_DIR" 2>/dev/null; then
 # Sanity check: launcher must exist on PATH after install.
 if command -v minxg >/dev/null 2>&1; then
 printf " \033[32m✓\033[0m global command registered: $(command -v minxg)\n"
 else
 # Fall back to: python -m multiligua_cli (always works).
 printf " \033[33m⚠\033[0m pip install -e . succeeded but minxg is not on PATH\n"
 echo " use: python3 -m multiligua_cli <command>"
 echo " : export PATH=\"\$HOME/.local/bin:\$PATH\""
 fi
 else
 printf " \033[33m⚠\033[0m pip install -e . failed\n"
 echo " : cd '$SCRIPT_DIR' && python3 -m pip install -e ."
 fi
else
 printf " \033[33m⚠\033[0m pyproject.toml not found; skipping\n"
fi

# ── C/C++ ─────────────────────────────────────
echo "[4/6] building native library..."
NATIVE_OK=false

# cpp_core (CMake) produces libminxg_core.so + libminxg_cpp_json.so.
# These are REQUIRED for the in-process core path; a pythonnative
# fallback keeps the CLI usable, but TUI chats will degrade to
# pure-python hashes / encoders if we skip this step.
if [ -d "$SCRIPT_DIR/cpp_core" ] && [ -f "$SCRIPT_DIR/cpp_core/CMakeLists.txt" ]; then
 if command -v cmake >/dev/null 2>&1; then
  echo " → cmake: $SCRIPT_DIR/cpp_core"
  mkdir -p "$SCRIPT_DIR/cpp_core/build"
  (cd "$SCRIPT_DIR/cpp_core/build" && cmake .. >/dev/null 2>&1 \
   && make -j4 >/dev/null 2>&1) && {
   echo " ✅ libminxg_core.so, libminxg_cpp_json.so"
   NATIVE_OK=true
  } || {
   printf " \033[33m⚠\033[0m cpp_core cmake build failed (using pure-Python fallback)\n"
  }
 else
  printf " \033[33m⚠\033[0m cmake not found; install: pkg install cmake / apt install cmake\n"
  printf " \033[33m⚠\033[0m cpp_core skipped (pure-Python fallback)\n"
 fi
fi

# Optional in-tree self-evolution engine + text engine (c_core).
# Build only when compiler + dev libs are present. These are tied
# to the historical libminxg_evolve.so artefact; cpp_core supersedes
# them functionally.
if [ -d "$SCRIPT_DIR/c_core" ]; then
 if command -v gcc >/dev/null 2>&1 || command -v clang >/dev/null 2>&1; then
  mkdir -p "$SCRIPT_DIR/build"
  CC=${CC:-gcc}
  CFLAGS="-std=c11 -O3 -fPIC -shared"

  if [ -f "$SCRIPT_DIR/c_core/minxg_evolve.c" ]; then
   echo " → c_core/minxg_evolve.c (legacy, optional)"
   (cd "$SCRIPT_DIR/c_core" \
    && $CC $CFLAGS minxg_evolve.c -lxxhash -lzstd -lm -lpthread \
       -o "$SCRIPT_DIR/build/libminxg_evolve.so") 2>/dev/null \
    && echo " ✅ libminxg_evolve.so" \
    || printf " \033[33m⚠\033[0m libminxg_evolve build skipped (no xxhash/zstd dev libs)\n"
  fi
  if [ -f "$SCRIPT_DIR/c_core/text_engine.c" ]; then
   echo " → c_core/text_engine.c (legacy, optional)"
   (cd "$SCRIPT_DIR/c_core" \
    && $CC $CFLAGS text_engine.c -lm -lpthread \
       -o "$SCRIPT_DIR/build/libtext_engine.so") 2>/dev/null \
    && echo " ✅ libtext_engine.so" \
    || printf " \033[33m⚠\033[0m libtext_engine build skipped\n"
  fi
 else
  printf " \033[33m⚠\033[0m no C compiler (gcc/clang); legacy c_core skipped\n"
  echo " install: pkg install clang (Termux) apt install gcc (Linux)"
 fi
fi

# Android: surface built .so on syslib so dlopen() finds it without PATH=magic.
if [ "$PLATFORM" = "android" ] && [ -d "$SCRIPT_DIR/cpp_core/build" ]; then
 LIBDIR="/data/data/com.termux/files/usr/lib"
 for so in "$SCRIPT_DIR/cpp_core/build/"*.so "$SCRIPT_DIR/build/"*.so; do
  [ -f "$so" ] && cp "$so" "$LIBDIR/" 2>/dev/null \
   && echo " → copied: $(basename "$so")"
 done
fi

if [ "$NATIVE_OK" = true ]; then
 printf " \033[32m✓\033[0m python fallback enabled\n"
else
 printf " \033[33m⚠\033[0m native build unavailable; pure-Python fallback only\n"
fi

# ── py_compile ──────────────────────────────────────
echo "[5/6] checking python source compiles..."
cd "$SCRIPT_DIR"
PASS=0
FAIL=0
for f in $(find . -name '*.py' -not -path './.git/*' -not -path './build/*' -not -path './var/*' -not -path './build_asan/*' -not -path '*/__pycache__/*' -not -path '*/cpp_core/build/*'); do
 if python3 -m py_compile "$f" 2>/dev/null; then
 PASS=$((PASS + 1))
 else
 FAIL=$((FAIL + 1))
 [ $FAIL -le 5 ] && echo " ❌ $f"
 fi
done
echo " py_compile: $PASS/$((PASS + FAIL)) "
[ $FAIL -gt 0 ] && echo " ⚠️ $FAIL compile errors"

# ── tool registration ────────────────────────────────────────
echo "[6/6] extension self-check..."
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from extensions.loader import discover_extensions, list_extensions
exts = list_extensions()
active = sum(1 for e in exts if 'INACTIVE' not in e.get('description',''))
total = len(exts)
print(f' extensions total: {total} (active: {active}, inactive: {total-active})')
for e in exts:
 d = e.get('description','')
 s = '✅' if 'INACTIVE' not in d else '❌'
 print(f' {s} {e[\"name\"]:20s} {d[:60]}')
" 2>/dev/null || echo " ⚠ extension self-check skipped (import problem)"

# ── completion banner ──────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
printf " \033[32m✓\033[0m install complete\n"
echo "════════════════════════════════════════"
echo ""
echo " platform: $PLATFORM"
echo " python: $(python3 --version 2>&1)"
if [ "$NATIVE_OK" = true ]; then printf " native: \u001b[32mC/C++\u001b[0m\n"; else printf " native: python fallback\n"; fi
echo ""
echo " common commands:"
echo " minxg start the TUI chat"
echo " minxg ext list show installed extensions"
echo " minxg ext add <slug> install an extension"
echo " minxg ext add minxg-adb install ADB tools (opt-in)"
echo " minxg ext add minxg-root install ROOT tools (opt-in)"
echo " minxg doctor self-check"
echo ""
echo " (the old ADB/Root auto-detect steps were removed in 0.11; install"
echo " those extensions only when you need them — see 'minxg ext available'.)"

# ── Termux / ZeroTermux notification ───────────────────────────
# Fire AND-log only when we're inside Termux (NOT just Android).
# On every other platform this is a no-op — Windows/Mac/Linux users
# never see anything even when --notify is set, by design: Termux-API
# is a Termux-only stack and there's no equivalent portable backend.
if [ "${MINXG_NOTIFY:-0}" = "1" ]; then
 python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
try:
    from src.ai.notify import termux
    if termux.notify_task_completed(
        title='MINXG install done',
        body='platform=$PLATFORM · native=$NATIVE_OK',
    ):
        print(' 📱 notification sent (Termux/ZeroTermux)')
    else:
        print(' (skip notify: not in Termux)')
except Exception as e:
    print(f' (notify skipped: {e})')
" 2>/dev/null || true
fi