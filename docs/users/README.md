# MINXG User Guide

For a quick start see [README.md](../../README.md) and
[DEVELOPER.md](../../DEVELOPER.md) at the repo root.

## A short tour

```python
import minxg

print(minxg.VERSION)         # "1.2.0"
print(minxg.detect_platform())

fs = minxg.FsIoWorker()
result = await fs.list_directory(path="/tmp")
```

Where to go next:

* [DEVELOPER.md section 5](../../DEVELOPER.md#5-worker-base-class) — worker base class
* [DEVELOPER.md section 13](../../DEVELOPER.md#13-v120--self-developed-subsystems) — v1.2.0 subsystems
* [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — architecture
* [docs/DRIVER.md](../DRIVER.md) — driver engine
