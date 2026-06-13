# Tidal Lock — C 加速核心

> 10-100x 热路径加速。

## 11 个锁定的函数

1. `tl_isg_hash`
2. `tl_ncd_compute`
3. `tl_ncd_batch`
4. `tl_zstd_compress`
5. `tl_zstd_decompress`
6. `tl_xxhash3`
7. `tl_phase_embed`
8. `tl_drift_compute`
9. `tl_persistence_score`
10. `tl_behavior_classify`
11. `tl_entropy_compute`

## 性能

| 函数 | Python | Tidal Lock | 加速比 |
|------|--------|------------|--------|
| NCD (1KB) | 850 μs | 12 μs | 70x |
| 相空间嵌入 | 1.2 ms | 45 μs | 27x |
| zstd 压缩 | 320 μs | 18 μs | 18x |
| xxhash3 | 0.5 μs | 0.02 μs | 25x |

## 构建 & 加载

```bash
cd c_core && make
```

```python
from minxg._tidal_lock_bridge import get_tidal_lock
tl = get_tidal_lock()
if tl.is_loaded:
    ncd = tl.ncd_compute(a, b)
```

## 为何 "Tidal Lock"?

稳定状态 —— 旋转与轨道周期匹配。核心和包装被"锁定"在稳定接口上。
