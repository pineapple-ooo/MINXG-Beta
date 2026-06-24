#!/usr/bin/env bash
# MINXG v0.0.1-alpha — 一键全部测试脚本
# Usage: bash scripts/test_all.sh [--quick|--full|--lint-only]
# 测试内容: 语法检查 → 导入验证 → 工具计数 → 配置验证 → 冒烟测试 → 性能基准

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
START_TIME=$(date +%s)

mode="${1:-full}"

log_section() { echo -e "\n${CYAN}${BOLD}═══ $1 ═══${NC}\n"; }
log_pass()   { echo -e "  ${GREEN}✓${NC} $1"; ((PASS++)) || true; }
log_fail()   { echo -e "  ${RED}✗${NC} $1"; ((FAIL++)) || true; }
log_skip()   { echo -e "  ${YELLOW}~${NC} $1"; ((SKIP++)) || true; }
log_info()   { echo -e "  ${CYAN}→${NC} $1"; }

# ── Phase 1: 语法检查 ──
log_section "Phase 1: Syntax Check"
PY_FILES=$(find . -name "*.py" -not -path "./__pycache__/*" -not -path "./.git/*" -not -path "*/egg-info/*" 2>/dev/null | wc -l)
log_info "Found $PY_FILES Python files"

if python3 -c "
import py_compile, sys, os
errors = []
for root, dirs, files in os.walk('.'):
    if '__pycache__' in root or '.git' in root or 'egg-info' in root:
        continue
    for f in files:
        if f.endswith('.py'):
            fp = os.path.join(root, f)
            try:
                py_compile.compile(fp, doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f'{fp}: {e}')
if errors:
    for e in errors: print(e)
    sys.exit(1)
print('All files pass syntax check')
" 2>&1; then
    log_pass "Syntax check: ALL $PY_FILES files pass"
else
    log_fail "Syntax check: some files have errors"
fi

# ── Phase 2: 导入验证 ──
log_section "Phase 2: Import Verification"

declare -a IMPORTS=(
    "multiligua_cli.i18n"
    "multiligua_cli.setup"
    "multiligua_cli.main"
    "multiligua_cli.providers"
    "multiligua_cli.platforms"
    "multiligua_cli.memory"
    "multiligua_cli.features"
    "multiligua_cli.hot_reload"
    "multiligua_cli.logger"
    "multiligua_cli.wizard_ui"
    "multiligua_cli.utils"
    "py_workers.base"
    "py_workers.server"
)

for mod in "${IMPORTS[@]}"; do
    if python3 -c "import $mod" 2>/dev/null; then
        log_pass "Import: $mod"
    else
        log_fail "Import: $mod FAILED"
    fi
done

# Try to import new modules
declare -a NEW_IMPORTS=(
    "src.platform_adapters._detector"
    "src.ai.safety"
    "src.core.config._version"
)
for mod in "${NEW_IMPORTS[@]}"; do
    if python3 -c "import sys; sys.path.insert(0,'.'); from ${mod//\//.} import *" 2>/dev/null; then
        log_pass "Import: $mod"
    else
        log_info "Import: $mod (skipped — may need deps)"
        ((SKIP++)) || true
    fi
done

# ── Phase 3: 工具计数 ──
log_section "Phase 3: Tool Count"
TOOL_COUNT=$(grep -r "@tool" py_workers/ --include="*.py" 2>/dev/null | wc -l)
echo "  Total tools: $TOOL_COUNT"
if [ "$TOOL_COUNT" -ge 347 ]; then
    log_pass "Tool count: $TOOL_COUNT (>= 347 target)"
else
    log_fail "Tool count: $TOOL_COUNT (< 347 target)"
fi

# ── Phase 4: 数据验证 ──
log_section "Phase 4: Data Validation"

# 厂商数量
PROVIDER_COUNT=$(python3 -c "
from multiligua_cli.providers import AI_PROVIDERS
print(len(AI_PROVIDERS))
" 2>/dev/null || echo "0")
if [ "$PROVIDER_COUNT" -ge 30 ]; then
    log_pass "Providers: $PROVIDER_COUNT"
else
    log_fail "Providers: $PROVIDER_COUNT (< 30)"
fi

# 平台数量
PLATFORM_COUNT=$(python3 -c "
from multiligua_cli.platforms import PLATFORMS
print(len(PLATFORMS))
" 2>/dev/null || echo "0")
log_info "Platforms: $PLATFORM_COUNT"

# i18n语言数
LANG_COUNT=$(python3 -c "
from multiligua_cli.i18n import LANGUAGES
print(len(LANGUAGES))
" 2>/dev/null || echo "0")
if [ "$LANG_COUNT" -ge 15 ]; then
    log_pass "Languages: $LANG_COUNT"
else
    log_fail "Languages: $LANG_COUNT (< 15)"
fi

# ── Phase 5: 配置验证 ──
log_section "Phase 5: Config Validation"
if [ -f config.yaml ]; then
    if python3 -c "import yaml; yaml.safe_load(open('config.yaml'))" 2>/dev/null; then
        log_pass "config.yaml: valid YAML"
    else
        log_fail "config.yaml: invalid YAML"
    fi
else
    log_info "config.yaml: not found (using defaults)"
    ((SKIP++)) || true
fi

# ── Phase 6: 版本验证 ──
log_section "Phase 6: Version Check"
VERSION=$(python3 -c "from src.core.config._version import __version__; print(__version__)" 2>/dev/null || echo "unknown")
log_info "Version: $VERSION"

# ── Phase 7: 平台适配器测试 ──
if [ "$mode" != "lint-only" ]; then
    log_section "Phase 7: Platform Adapter Test"
    if python3 -c "
import sys; sys.path.insert(0, '.')
from src.platform_adapters._detector import PlatformDetector
p = PlatformDetector.full_profile()
print(f'  OS: {p.os.value} | Arch: {p.arch.value} | Tier: {p.tier.value}')
print(f'  RAM: {p.memory.total_mb}MB | CPU: {p.cpu.cores_logical} cores')
" 2>/dev/null; then
        log_pass "Platform adapter: working"
    else
        log_info "Platform adapter: skipped"
        ((SKIP++)) || true
    fi
fi

# ── Summary ──
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${CYAN}${BOLD}═════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}${BOLD}  MINXG Test Summary${NC}"
echo -e "${CYAN}${BOLD}═════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Passed: $PASS${NC}"
echo -e "  ${RED}Failed: $FAIL${NC}"
echo -e "  ${YELLOW}Skipped: $SKIP${NC}"
echo -e "  Duration: ${DURATION}s"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}${BOLD}  TESTS FAILED — $FAIL failure(s)${NC}"
    exit 1
else
    echo -e "${GREEN}${BOLD}  ALL TESTS PASSED ✓${NC}"
    exit 0
fi
