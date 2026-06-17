# INSTALL

> 安装 MINXG. See [README.md](README.md) for English, or one of the
> language-specific READMEs for other languages.

---

## 1 · Quick install (pure Python)

```bash
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

That's it. The six mathematical pillars work out of the box, no
external C/C++/Go needed.

## 2 · Full install (with acceleration cores)

```bash
# C core (Tidal Lock)
cd c_core && make && cd ..

# C++ utilities
cd cpp_core && mkdir -p build && cd build && cmake .. && make && cd ../..

# Go acceleration
cd go_core && go build ./... && cd ..

# Install with all extras
pip install -e ".[dev]"
```

## 3 · Termux / Android (verified)

This project is fully tested on Termux:

```bash
pkg install python git cmake golang
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

`minxg/core_native.py` auto-detects Termux and copies any prebuilt
`.so` files to a writable location before loading them (bypassing
Android's linker namespace restriction).

## 4 · Linux

```bash
# Ubuntu / Debian
sudo apt install python3 python3-pip cmake golang
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

## 5 · macOS

```bash
brew install python@3.11 cmake go
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

## 6 · Verify

```bash
python3 -c "
import minxg
from minxg.operators import OPERATOR_REGISTRY
print(f'{OPERATOR_REGISTRY.total_operators} operators')
for cat, count in sorted(OPERATOR_REGISTRY.category_summary().items()):
    print(f'  {cat:10s} {count:>4d}')
print(f'Mathematical pillars: {minxg.get(\"pillars\")}')
"
```

Expected:

```
376 operators
       cat  79
     chaos  23
       data  12
      fiber  53
        ga  47
   infogeo  51
     logic  13
      math  20
     system   6
      text  19
      topo  53
Mathematical pillars: [...]
```

## 7 · Next steps

- [QUICKSTART.md](QUICKSTART.md) — 5-minute tour of all 6 pillars
- [ARCHITECTURE.md](ARCHITECTURE.md) — full system architecture
- [PROJECT_INDEX.md](PROJECT_INDEX.md) — one-page project map
