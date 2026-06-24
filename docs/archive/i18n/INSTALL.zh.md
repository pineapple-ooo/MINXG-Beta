# 安装

## 1 · 快速安装(纯 Python)

```bash
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

## 2 · 完整安装(带加速核心)

```bash
cd c_core && make && cd ..
cd cpp_core && mkdir -p build && cd build && cmake .. && make && cd ../..
cd go_core && go build ./... && cd ..
pip install -e ".[dev]"
```

## 3 · Termux / Android

```bash
pkg install python git cmake golang
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

## 4 · Linux / macOS

```bash
sudo apt install python3 python3-pip cmake golang  # Linux
brew install python@3.11 cmake go                   # macOS
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

## 5 · 验证

```bash
python3 -c "
import minxg
from minxg.operators import OPERATOR_REGISTRY
print(f'{OPERATOR_REGISTRY.total_operators} 算子')
"
```

## 6 · 下一步

- [QUICKSTART.md](QUICKSTART.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
