#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════
#  MINXG v1.0.0 — 自动安装脚本 (全平台)
#
#  用法:
#    本地:    bash install.sh                              # clone 模式自动跳过
#    远程:    curl -fsSL https://REPO/install.sh | bash    # 自动 clone 到 ~/.minxg-src
#    指定仓库: curl -fsSL https://REPO/install.sh | bash -s -- https://x/y.git
#    指定分支: curl -fsSL https://REPO/install.sh | bash -s -- --branch main
#    指定目录: curl -fsSL https://REPO/install.sh | bash -s -- --dir /opt/minxg
#
#  注意: REPO_URL 默认值见下。把它改成你的真实仓库 URL 即可一行安装。
# ═══════════════════════════════════════════════════════════════
set -e

# ── 自文档: --help / -h ─────────────────────────────────
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat <<'USAGE'
MINXG install.sh — bootstrap a fresh machine with one command.

USAGE:
    bash install.sh                    # local repo mode (auto-detect)
    curl -fsSL <host>/install.sh | bash              # clone defaults
    curl -fsSL <host>/install.sh | bash -s -- ARG... # pass extra args

ARGUMENTS (positional, evaluated in order; env vars win when set):
    $1   repo URL       (env: REPO_URL)        default: see header
    $2   install dir    (env: MINXG_DIR)        default: $HOME/.minxg-src
    $3   git branch     (env: MINXG_BRANCH)     default: (default branch)

OPTIONS:
    --help, -h         show this message and exit

ENVIRONMENT:
    REPO_URL           override the default clone URL
    MINXG_DIR          change the clone destination (avoids an existing dir)
    MINXG_BRANCH       pin a branch / tag to clone
    PYTHON             python interpreter to use (default: python3)

EXAMPLES:
    # fresh machine, one line:
    curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh | bash

    # fork:
    REPO_URL=https://github.com/you/minxg.git bash install.sh

    # already cloned:
    cd minxg && bash install.sh

The script is self-contained: no external config, no env required.
USAGE
    exit 0
fi

# ── 配置 — 把这里改成你的真实仓库 URL ───────────────────
# 优先级: $1 > $REPO_URL > 内置默认. 注意管道模式 ($1="") 时必须看 env.
REPO_URL_DEFAULT="https://github.com/Disability-Human/MINXG-Beta.git"
REPO_URL="${1:-${REPO_URL:-$REPO_URL_DEFAULT}}"
INSTALL_DIR="${MINXG_DIR:-${2:-$HOME/.minxg-src}}"
CLONE_BRANCH="${MINXG_BRANCH:-${3:-}}"
# ───────────────────────────────────────────────────────

echo "════════════════════════════════════════"
echo "  MINXG v1.0.0 自动安装"
echo "════════════════════════════════════════"
echo ""

# ── 检测管道模式 vs 本地模式 ────────────────────────────
# 关键: 管道模式下 $0 和 BASH_SOURCE[0] 都是 "bash" 或 "/dev/stdin" (或空),
#       dirname 拿不到真实路径, $SCRIPT_DIR 无效, 必须 git clone。
# 判定优先级:
#   1. BASH_SOURCE[0] 是个真实存在的文件 → 本地模式
#   2. -t 0 (stdin=tty) → 本地模式
#   3. 其余 → 管道模式
LOCAL_MODE=true
BS0="${BASH_SOURCE[0]:-}"
# 1) 文件存在则本地模式
if [ -n "$BS0" ] && [ -f "$BS0" ]; then
    LOCAL_MODE=true
# 2) stdin 连着 tty → 本地模式
elif [ -t 0 ]; then
    LOCAL_MODE=true
# 3) 其它 (curl|bash / bash < script / heredoc) → 管道模式
else
    LOCAL_MODE=false
fi

if [ "$LOCAL_MODE" = true ]; then
    SCRIPT_DIR="$(cd "$(dirname "$BS0")" && pwd)"
    echo "  模式: 本地 (SCRIPT_DIR = $SCRIPT_DIR)"
else
    echo "  模式: 远程一行安装 (curl | bash)"
    echo "  仓库: $REPO_URL"
    echo "  目录: $INSTALL_DIR"
    echo ""

    # 必须有 git + curl 二者之一. 没有就给安装提示并退出.
    if ! command -v git >/dev/null 2>&1; then
        echo "  ❌ 管道模式需要 git 才能 clone 仓库"
        case "$(uname -s)" in
            Linux)
                if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ]; then
                    echo "     安装: pkg install git"
                else
                    echo "     安装: sudo apt install git"
                fi
                ;;
            Darwin)  echo "     安装: brew install git  (或 xcode-select --install)" ;;
            MINGW*|MSYS*|CYGWIN*) echo "     下载: https://git-scm.com/download/win" ;;
        esac
        exit 1
    fi
    if ! command -v curl >/dev/null 2>&1; then
        echo "  ❌ 管道模式需要 curl"
        echo "     (其实你已经用 curl 跑了本脚本, 怎么会没有 curl? 检查 PATH)"
        exit 1
    fi

    mkdir -p "$INSTALL_DIR"
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "  [0/8] 更新现有仓库: $INSTALL_DIR"
        if [ -n "$CLONE_BRANCH" ]; then
            git -C "$INSTALL_DIR" fetch --depth 1 origin "$CLONE_BRANCH" >/dev/null 2>&1 || true
            git -C "$INSTALL_DIR" checkout "$CLONE_BRANCH" >/dev/null 2>&1 || true
        else
            git -C "$INSTALL_DIR" pull --ff-only 2>&1 | tail -3 || true
        fi
    else
        echo "  [0/8] 克隆仓库到: $INSTALL_DIR"
        CLONE_ARGS=(--depth 1)
        if [ -n "$CLONE_BRANCH" ]; then
            CLONE_ARGS+=(--branch "$CLONE_BRANCH")
        fi
        # repo 可能已存在但不是 git 仓库 (空目录) — 清掉重来
        if [ -d "$INSTALL_DIR" ] && [ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
            echo "  ❌ $INSTALL_DIR 已存在且非空, 不是 git 仓库."
            echo "     手动指定目录: MINXG_DIR=/path/to/clean/dir"
            exit 1
        fi
        if ! git clone "${CLONE_ARGS[@]}" "$REPO_URL" "$INSTALL_DIR"; then
            echo "  ❌ clone 失败: $REPO_URL"
            echo "     检查网络 / 仓库地址 / 权限"
            exit 1
        fi
    fi
    echo "  ✅ 仓库就绪"
    echo ""
    SCRIPT_DIR="$INSTALL_DIR"
fi

# ── 检测平台 ────────────────────────────────────────────
detect_platform() {
    case "$(uname -s)" in
        Linux)
            if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ]; then
                echo "android"
            else
                echo "linux"
            fi
            ;;
        Darwin)  echo "macos" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)       echo "unknown" ;;
    esac
}

PLATFORM=$(detect_platform)
echo "  检测到平台: $PLATFORM"
echo ""

# ── 检查Python ──────────────────────────────────────────
echo "[1/8] 检查 Python..."
python3 --version || {
    echo ""
    echo "  ❌ 需要 Python 3.10+"
    case "$PLATFORM" in
        android)
            echo "  安装: pkg install python"
            ;;
        linux)
            echo "  安装: sudo apt install python3 python3-pip"
            ;;
        macos)
            echo "  安装: brew install python@3"
            ;;
    esac
    exit 1
}
echo "  ✅ Python: $(python3 --version)"

# ── 安装Python依赖 ──────────────────────────────────────
echo "[2/8] 安装 Python 依赖..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip install -q --disable-pip-version-check -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || {
        echo "  ⚠️  部分依赖安装失败，继续..."
    }
else
    pip install -q --disable-pip-version-check pip --upgrade 2>/dev/null || true
fi
echo "  ✅ 依赖安装完成"

# ── 注册 console_script 入口 (全局 `minxg` 命令) ────────
# Why: pyproject.toml defines `[project.scripts] minxg = "multiligua_cli.main:main"`.
# Without this step, the `minxg` command is not on PATH anywhere, so the user has to
# type `python3 -m multiligua_cli` after every install. `pip install -e .` reads the
# entry-points table and drops a launcher in $(python -m site --user-base)/bin
# (or termux-prefix/usr/bin) so `minxg --help` works from any directory.
echo "[3/8] 注册全局命令 (pip install -e .)..."
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    # Prefer the python that ships the deps we just installed.
    PY_FOR_INSTALL="${PYTHON:-python3}"
    if "$PY_FOR_INSTALL" -m pip install -q --disable-pip-version-check -e "$SCRIPT_DIR" 2>/dev/null; then
        # Sanity check: launcher must exist on PATH after install.
        if command -v minxg >/dev/null 2>&1; then
            echo "  ✅ 全局命令已注册: $(command -v minxg)"
        else
            # Fall back to: python -m multiligua_cli (always works).
            echo "  ⚠️  pip install -e . 成功，但 minxg 不在 PATH"
            echo "      使用: python3 -m multiligua_cli <命令>"
            echo "      或手动: export PATH=\"\$HOME/.local/bin:\$PATH\""
        fi
    else
        echo "  ⚠️  pip install -e . 失败"
        echo "      手动命令: cd '$SCRIPT_DIR' && python3 -m pip install -e ."
    fi
else
    echo "  ⚠️  未找到 pyproject.toml，跳过"
fi

# ── 编译C/C++原生库 ─────────────────────────────────────
echo "[4/8] 编译原生库..."
NATIVE_OK=false

if [ -d "$SCRIPT_DIR/c_core" ]; then
    cd "$SCRIPT_DIR/c_core"
    if command -v gcc >/dev/null 2>&1 || command -v clang >/dev/null 2>&1; then
        CC=${CC:-gcc}
        CFLAGS="-std=c11 -O3 -fPIC -shared"

        # minxg_evolve.c — self-evolution engine
        if [ -f "minxg_evolve.c" ]; then
            echo "  编译 minxg_evolve..."
            $CC $CFLAGS minxg_evolve.c -lxxhash -lzstd -lm -lpthread \
                -o "$SCRIPT_DIR/build/libminxg_evolve.so" 2>/dev/null && {
                echo "  ✅ libminxg_evolve.so"
                NATIVE_OK=true
            } || {
                echo "  ⚠️  libminxg_evolve 编译失败 (无 xxhash/zstd 开发库)"
            }
        fi

        # text_engine.c — text processing
        if [ -f "text_engine.c" ]; then
            echo "  编译 text_engine..."
            $CC $CFLAGS text_engine.c -lm -lpthread \
                -o "$SCRIPT_DIR/build/libtext_engine.so" 2>/dev/null && {
                echo "  ✅ libtext_engine.so"
            } || echo "  ⚠️  text_engine 编译失败"
        fi
    else
        echo "  ⚠️  未找到C编译器 (gcc/clang)，跳过原生库编译"
        echo "      安装: pkg install clang (Termux) 或 apt install gcc (Linux)"
    fi
    cd "$SCRIPT_DIR"
fi

# Android特殊处理: 复制.so到系统库目录
if [ "$PLATFORM" = "android" ] && [ "$NATIVE_OK" = true ]; then
    LIBDIR="/data/data/com.termux/files/usr/lib"
    for so in "$SCRIPT_DIR/build/"*.so; do
        [ -f "$so" ] && cp "$so" "$LIBDIR/" 2>/dev/null && echo "  → 已复制: $(basename $so)"
    done
fi

echo "  $( [ "$NATIVE_OK" = true ] && echo '✅ 原生库编译成功' || echo '⚠️  无原生加速 (Python fallback可用)')"

# ── 检测ADB ─────────────────────────────────────────────
echo "[5/8] 检测 ADB..."
if command -v adb >/dev/null 2>&1; then
    echo "  ✅ ADB: $(adb version 2>&1 | head -1)"

    # 检测设备
    DEVICES=$(adb devices 2>/dev/null | grep -v "List" | grep -c "device" || echo 0)
    if [ "$DEVICES" -gt 0 ]; then
        echo "  ✅ 已连接设备: $DEVICES 台"
        echo "     → ADB扩展自动启用 (9个AI工具)"
    else
        echo "  ⚠️  无设备连接"
        echo "     → USB连接手机后，ADB扩展自动启用"
    fi
else
    echo "  ❌ ADB未检测到"
    echo ""
    echo "  安装ADB后，扩展自动启用:"
    case "$PLATFORM" in
        android) echo "    pkg install android-tools" ;;
        linux)   echo "    sudo apt install android-tools-adb" ;;
        macos)   echo "    brew install android-platform-tools" ;;
    esac
fi

# ── 检测ROOT ─────────────────────────────────────────────
echo "[6/8] 检测 ROOT..."
ROOT_OK=false
for su in /system/bin/su /system/xbin/su /sbin/su /su/bin/su /magisk/.core/bin/su; do
    if [ -f "$su" ] && [ -x "$su" ]; then
        ROOT_OK=true
        echo "  ✅ ROOT: $su"
        break
    fi
done

if [ "$ROOT_OK" = false ]; then
    # 尝试运行su
    if command -v su >/dev/null 2>&1; then
        if su -c "echo ok" 2>/dev/null | grep -q ok; then
            ROOT_OK=true
            echo "  ✅ ROOT: su可用"
        fi
    fi
fi

if [ "$ROOT_OK" = true ]; then
    echo "     → ROOT扩展自动启用 (9个AI工具)"
else
    echo "  ❌ 设备未ROOT"
    echo "     → ROOT扩展禁用"
    echo "     获取ROOT: Magisk / SuperSU"
fi

# ── py_compile 验证 ─────────────────────────────────────
echo "[7/8] 验证代码..."
cd "$SCRIPT_DIR"
PASS=0
FAIL=0
for f in $(find . -name '*.py' -not -path './.git/*' -not -path './build/*' -not -path './var/*'); do
    if python3 -m py_compile "$f" 2>/dev/null; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        [ $FAIL -le 3 ] && echo "  ❌ $f"
    fi
done
echo "  py_compile: $PASS/$((PASS + FAIL)) 通过"
[ $FAIL -gt 0 ] && echo "  ⚠️  $FAIL 个文件有语法错误"

# ── 扩展自检 ────────────────────────────────────────────
echo "[8/8] 扩展自检..."
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from extensions.loader import discover_extensions, list_extensions
exts = list_extensions()
active = sum(1 for e in exts if 'INACTIVE' not in e.get('description',''))
total = len(exts)
print(f'  扩展总数: {total} (启用: {active}, 未激活: {total-active})')
for e in exts:
    d = e.get('description','')
    s = '✅' if 'INACTIVE' not in d else '❌'
    print(f'    {s} {e[\"name\"]:20s} {d[:60]}')
" 2>/dev/null || echo "  ⚠️  扩展自检跳过 (模块导入问题)"

# ── 总结 ────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  安装完成！"
echo "════════════════════════════════════════"
echo ""
echo "  平台:       $PLATFORM"
echo "  Python:     $(python3 --version 2>&1)"
echo "  原生加速:   $( [ "$NATIVE_OK" = true ] && echo '✅ C/C++' || echo '⚠️ Python fallback')"
echo "  ADB:        $(command -v adb >/dev/null 2>&1 && echo '✅ 就绪' || echo '❌ 未安装')"
echo "  ROOT:       $( [ "$ROOT_OK" = true ] && echo '✅ 就绪' || echo '❌ 未ROOT')"
echo ""
echo "  常用命令:"
echo "    minxg start          启动"
echo "    minxg ext list       查看扩展"
echo "    minxg ext import     导入扩展包"
echo "    minxg ext adb        使用ADB工具"
echo "    minxg ext root       使用ROOT工具"
echo ""