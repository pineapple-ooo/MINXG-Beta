#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════
#  MINXG v1.0.0 — 自动安装脚本 (全平台)
# ═══════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "════════════════════════════════════════"
echo "  MINXG v1.0.0 自动安装"
echo "════════════════════════════════════════"
echo ""

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
echo "[1/7] 检查 Python..."
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
echo "[2/7] 安装 Python 依赖..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip install -q -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || {
        echo "  ⚠️  部分依赖安装失败，继续..."
    }
else
    pip install -q pip --upgrade 2>/dev/null || true
fi
echo "  ✅ 依赖安装完成"

# ── 编译C/C++原生库 ─────────────────────────────────────
echo "[3/7] 编译原生库..."
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
echo "[4/7] 检测 ADB..."
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
echo "[5/7] 检测 ROOT..."
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
echo "[6/7] 验证代码..."
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
echo "[7/7] 扩展自检..."
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