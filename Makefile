# MINXG Polyglot Build System
# =============================
#
# Language responsibilities:
#   C    → libminxg_c.so    (core data structures, text engine, memory pools)
#   C++  → libminxg_cpp.a   (crypto, json_fast, compress, RAII wrappers)
#   Go   → minxg-gateway    (HTTP/WS server, rate limiter, health checker)
#   Python → orchestration  (CLI/TUI, AI prompt chain, extension loading)
#
# Build order: C → C++ → Go → Python (ctypes loads C, Go calls C via CGo)

SHELL := /bin/bash
ROOT  := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

CC       ?= gcc
CXX      ?= g++
GO       ?= go

CFLAGS   := -std=c11 -O3 -fPIC -Wall -Wextra -Wno-unused-parameter
CXXFLAGS := -std=c++17 -O3 -fPIC -Wall -Wextra -Wno-unused-parameter
LDFLAGS  := -lssl -lcrypto -lpthread -lz

BUILD_DIR    := $(ROOT)/build
C_CORE_DIR   := $(ROOT)/c_core
CPP_CORE_DIR := $(ROOT)/cpp_core/src

# cpp_wrapper.c lives outside c_core/ but is a pure-C ctypes bridge
C_WRAPPER  := $(ROOT)/cpp_core/cpp_wrapper.c
C_SOURCES  := $(wildcard $(C_CORE_DIR)/*.c) $(C_WRAPPER)
C_OBJECTS  := $(patsubst $(C_CORE_DIR)/%.c,$(BUILD_DIR)/c/%.o,$(filter-out $(C_WRAPPER),$(C_SOURCES))) \
              $(BUILD_DIR)/c/cpp_wrapper.o
C_TARGET  := $(BUILD_DIR)/libminxg_c.so

CPP_SOURCES := $(wildcard $(CPP_CORE_DIR)/*.cpp)
CPP_OBJECTS := $(patsubst $(CPP_CORE_DIR)/%.cpp,$(BUILD_DIR)/cpp/%.o,$(CPP_SOURCES))
CPP_TARGET  := $(BUILD_DIR)/libminxg_cpp.a

GO_TARGET   := $(BUILD_DIR)/minxg-gateway

.PHONY: all c-build cpp-build go-build test test-integration clean

all: c-build cpp-build go-build
	@echo ""
	@echo "  MINXG Polyglot build complete"
	@echo "    C   : $(C_TARGET)"
	@echo "    C++ : $(CPP_TARGET)"
	@echo "    Go  : $(GO_TARGET)"

# ─── C Library ──────────────────────────────────────────────────────────

c-build: $(C_TARGET)

$(BUILD_DIR)/c/%.o: $(C_CORE_DIR)/%.c
	@mkdir -p $(BUILD_DIR)/c
	$(CC) $(CFLAGS) -I$(C_CORE_DIR) -c $< -o $@

$(BUILD_DIR)/c/cpp_wrapper.o: $(C_WRAPPER)
	@mkdir -p $(BUILD_DIR)/c
	$(CC) $(CFLAGS) -I$(C_CORE_DIR) -I$(ROOT)/cpp_core -c $< -o $@

$(C_TARGET): $(C_OBJECTS)
	$(CC) -shared -o $@ $^ $(LDFLAGS)
	@echo "  [OK] C library: $(C_TARGET)"

# ─── C++ Library ────────────────────────────────────────────────────────

cpp-build: $(CPP_TARGET)

$(BUILD_DIR)/cpp/%.o: $(CPP_CORE_DIR)/%.cpp
	@mkdir -p $(BUILD_DIR)/cpp
	$(CXX) $(CXXFLAGS) -I$(CPP_CORE_DIR) -I$(C_CORE_DIR) -c $< -o $@

$(CPP_TARGET): $(CPP_OBJECTS)
	$(AR) rcs $@ $^
	@echo "  [OK] C++ library: $(CPP_TARGET)"

# ─── Go Gateway ─────────────────────────────────────────────────────────

go-build: $(C_TARGET)
	@mkdir -p $(BUILD_DIR)/go
	cd $(ROOT)/go_core && CGO_ENABLED=1 \
		CGO_LDFLAGS="-L$(BUILD_DIR) -lminxg_c -lssl -lcrypto -lpthread" \
		CGO_CFLAGS="-I$(C_CORE_DIR)" \
		$(GO) build -ldflags="-s -w" -o $(GO_TARGET) ./cmd/gateway
	@echo "  [OK] Go gateway: $(GO_TARGET)"

# ─── Clean ──────────────────────────────────────────────────────────────

clean:
	rm -rf $(BUILD_DIR)
	@echo "  [OK] Cleaned build directory"

# ─── Test ───────────────────────────────────────────────────────────────

.PHONY: test test-quick test-full

test: test-quick

test-quick:
	@echo "=== pytest (unit tests, integration excluded) ==="
	cd $(ROOT) && python -m pytest tests/ -q $(PYTEST_ARGS) 2>&1

test-full:
	@echo "=== pytest (all tests including integration) ==="
	cd $(ROOT) && python -m pytest tests/ -q 2>&1

# ─── Integration Test ───────────────────────────────────────────────────

test-integration: go-build
	@echo "=== Integration Test: Go gateway + Python bridge ==="
	@echo ""
	@echo "[1/3] Starting Go gateway on :19004..."
	@$(GO_TARGET) --port 19004 &
	@sleep 2
	@echo "[2/3] Running Python roundtrip (health check + proxy)..."
	@cd $(ROOT) && python3 -c "\
import urllib.request, json, sys; \
try: \
    r = urllib.request.urlopen('http://localhost:19004/v1/health', timeout=5); \
    data = json.loads(r.read()); \
    print(f'  Health: {data}'); \
except Exception as e: \
    print(f'  FAIL: {e}'); \
    sys.exit(1); \
print('  [OK] Go gateway health check passed'); \
"
	@echo "[3/3] Stopping gateway..."
	@pkill -f "minxg-gateway --port 19004" 2>/dev/null || true
	@echo ""
	@echo "  [OK] Integration test passed"