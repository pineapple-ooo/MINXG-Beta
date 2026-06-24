# 扩展

> 构建自己的算子、worker、数学支柱。

## 1 · 添加新算子

```python
from minxg.operators import Operator, OPERATOR_REGISTRY

OPERATOR_REGISTRY.register(Operator(
    op_id=10000,
    name="my_op",
    category="custom",
    description="...",
    input_types=["number", "number"],
    output_type="number",
    is_pure=True,
    fn=lambda x, y: x * x + y * y,
))
```

## 2 · 添加新 Worker

```python
from minxg.base import BaseWorker, tool

class MyWorker(BaseWorker):
    name = "my_worker"

    @tool(description="...")
    def my_tool(self, x: float) -> float:
        return x ** 2

worker = MyWorker()
```

## 3 · 添加新数学支柱

1. 创建 `minxg/<pillar>/__init__.py`
2. 创建 `minxg/<pillar>/operators_<pillar>.py` 带 `register_<pillar>_operators()` 函数
3. 在 `minxg/__init__.py` 添加自动注册
4. 更新 `config/minxg.yaml`
5. 加 `minxg/<pillar>/README.md` (+ 4 语言)

## 4 · 完整扩展包

放入 `extensions/user/<name>/`。

## 5 · 热重载

```python
from minxg.hotreload import HotReloadWorker
hot = HotReloadWorker()
hot.enable()
```

## 6 · 新翻译

每文档 4 语言:`<doc>.md` `.zh.md` `.ja.md` `.ko.md`。
