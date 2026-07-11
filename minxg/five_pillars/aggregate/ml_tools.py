"""
"""
from __future__ import annotations
from typing import Dict, List
import math
from minxg.base import BaseWorker, tool


class MlToolsWorker(BaseWorker):
    facade_alias = "ml_tools"
    worker_id = "ml_tools"
    version = "0.17.1"

    @tool(description="Min-Max normalize array", category="preprocess")
    async def normalize(self, values: list, range_min: float = 0, range_max: float = 1) -> Dict:
        try:
            nums = [float(v) for v in values]
        except (ValueError, TypeError):
            return {"error": "values must be numeric"}
        vmin, vmax = min(nums), max(nums)
        if vmin == vmax:
            normalized = [range_min] * len(nums)
        else:
            normalized = [range_min + (x - vmin) / (vmax - vmin) * (range_max - range_min) for x in nums]
        return {"normalized": normalized, "original_min": vmin, "original_max": vmax,
                "target_range": [range_min, range_max]}

    @tool(description="Z-Score standardize", category="preprocess")
    async def standardize(self, values: list) -> Dict:
        try:
            nums = [float(v) for v in values]
        except (ValueError, TypeError):
            return {"error": "values must be numeric"}
        n = len(nums)
        mean = sum(nums) / n
        std = math.sqrt(sum((x - mean)**2 for x in nums) / n)
        if std == 0:
            standardized = [0.0] * n
        else:
            standardized = [(x - mean) / std for x in nums]
        return {"standardized": standardized, "mean": round(mean, 6), "std": round(std, 6)}

    @tool(description="Array stats: min/max/mean/std/median", category="stats")
    async def describe(self, values: list) -> Dict:
        try:
            nums = sorted([float(v) for v in values])
        except (ValueError, TypeError):
            return {"error": "values must be numeric"}
        n = len(nums)
        mean = sum(nums) / n
        std = math.sqrt(sum((x - mean)**2 for x in nums) / n)
        median = nums[n//2] if n % 2 else (nums[n//2-1] + nums[n//2]) / 2
        q1 = nums[n//4]
        q3 = nums[3*n//4]
        return {"count": n, "min": nums[0], "max": nums[-1],
                "mean": round(mean, 6), "std": round(std, 6),
                "median": median, "q1": q1, "q3": q3,
                "sum": round(sum(nums), 6), "range": nums[-1] - nums[0]}

    @tool(description="Split train/test indices", category="split")
    async def train_test_split(self, total: int, test_ratio: float = 0.2, seed: int = 42) -> Dict:
        import random
        rng = random.Random(seed)
        indices = list(range(total))
        rng.shuffle(indices)
        test_size = max(1, int(total * test_ratio))
        test_idx = sorted(indices[:test_size])
        train_idx = sorted(indices[test_size:])
        return {"total": total, "train_size": len(train_idx), "test_size": len(test_idx),
                "test_ratio": test_ratio, "train_indices": train_idx, "test_indices": test_idx}

    @tool(description="K-Fold cross validation indices", category="split")
    async def kfold_split(self, total: int, k: int = 5, seed: int = 42) -> Dict:
        import random
        rng = random.Random(seed)
        indices = list(range(total))
        rng.shuffle(indices)
        fold_size = total // k
        folds = []
        for i in range(k):
            start = i * fold_size
            end = start + fold_size if i < k - 1 else total
            test_idx = indices[start:end]
            train_idx = [x for j, x in enumerate(indices) if j < start or j >= end]
            folds.append({"fold": i+1, "train_indices": sorted(train_idx), "test_indices": sorted(test_idx)})
        return {"total": total, "k": k, "fold_size": fold_size, "folds": folds}

    @tool(description="Build confusion matrix metrics", category="evaluate")
    async def confusion_metrics(self, y_true: list, y_pred: list) -> Dict:
        if len(y_true) != len(y_pred):
            return {"error": "length mismatch"}
        labels = sorted(set(y_true) | set(y_pred))
        matrix = {l: {p: 0 for p in labels} for l in labels}
        tp = fp = tn = fn = 0
        for t, p in zip(y_true, y_pred):
            matrix[str(t)][str(p)] = matrix[str(t)].get(str(p), 0) + 1
            if len(labels) == 2:
                pos = labels[1]
                if t == pos and p == pos:
                    tp += 1
                elif t != pos and p == pos:
                    fp += 1
                elif t != pos and p != pos:
                    tn += 1
                elif t == pos and p != pos:
                    fn += 1
        result = {"matrix": matrix, "labels": labels}
        if len(labels) == 2:
            accuracy = (tp + tn) / max(1, tp + tn + fp + fn)
            precision = tp / max(1, tp + fp)
            recall = tp / max(1, tp + fn)
            f1 = 2 * precision * recall / max(0.001, precision + recall)
            result.update({"accuracy": round(accuracy, 4), "precision": round(precision, 4),
                           "recall": round(recall, 4), "f1": round(f1, 4)})
        return result

    @tool(description="Calculate cosine/euclidean/manhattan distance", category="distance")
    async def vector_distance(self, a: list, b: list, metric: str = "cosine") -> Dict:
        try:
            va = [float(x) for x in a]
            vb = [float(x) for x in b]
        except (ValueError, TypeError):
            return {"error": "vectors must be numeric"}
        if len(va) != len(vb):
            return {"error": "dimension mismatch"}
        if metric == "cosine":
            dot = sum(x*y for x, y in zip(va, vb))
            na = math.sqrt(sum(x*x for x in va))
            nb = math.sqrt(sum(x*x for x in vb))
            sim = dot / (na * nb) if na and nb else 1.0
            return {"metric": "cosine_similarity", "value": round(sim, 6)}
        elif metric == "euclidean":
            dist = math.sqrt(sum((x-y)**2 for x, y in zip(va, vb)))
            return {"metric": "euclidean_distance", "value": round(dist, 6)}
        elif metric == "manhattan":
            dist = sum(abs(x-y) for x, y in zip(va, vb))
            return {"metric": "manhattan_distance", "value": round(dist, 6)}
        return {"error": f"unknown metric: {metric}"}

    @tool(description="One-Hot encoding generation", category="encode")
    async def one_hot_encode(self, categories: list, value: str) -> Dict:
        unique = sorted(set(str(c) for c in categories))
        encoded = [1 if str(v) == value else 0 for v in unique]
        return {"categories": unique, "encoded": encoded, "value": value, "dimension": len(unique)}

    @tool(description="Learning rate schedule generation", category="training")
    async def lr_schedule(self, initial_lr: float = 0.001, total_steps: int = 1000,
                           schedule: str = "cosine") -> Dict:
        import math
        schedule = schedule.lower()
        milestones = {}
        for step in range(0, total_steps + 1, max(1, total_steps // 10)):
            if schedule == "cosine":
                lr = initial_lr * 0.5 * (1 + math.cos(math.pi * step / total_steps))
            elif schedule == "linear":
                lr = initial_lr * (1 - step / total_steps)
            elif schedule == "step":
                lr = initial_lr * (0.1 ** (step // (total_steps // 3)))
            else:
                lr = initial_lr
            milestones[f"step_{step}"] = round(lr, 8)
        return {"schedule": schedule, "initial_lr": initial_lr, "total_steps": total_steps,
                "milestones": milestones}

    @tool(description="Softmax calculation", category="math")
    async def softmax(self, values: list) -> Dict:
        try:
            nums = [float(v) for v in values]
        except (ValueError, TypeError):
            return {"error": "values must be numeric"}
        max_val = max(nums)
        exp_vals = [math.exp(x - max_val) for x in nums]
        total = sum(exp_vals)
        probs = [e / total for e in exp_vals]
        return {"probabilities": [round(p, 6) for p in probs],
                "sum": round(sum(probs), 6), "argmax": probs.index(max(probs))}

    @tool(description="Sigmoid calculation", category="math")
    async def sigmoid(self, value: float) -> Dict:
        s = 1 / (1 + math.exp(-value))
        return {"input": value, "output": round(s, 6),
                "note": "range (0, 1), midpoint at x=0 → 0.5"}

    @tool(description="Simple linear regression coefficients", category="regression")
    async def linear_regression(self, x: list, y: list) -> Dict:
        try:
            xs = [float(v) for v in x]
            ys = [float(v) for v in y]
        except (ValueError, TypeError):
            return {"error": "values must be numeric"}
        if len(xs) != len(ys) or len(xs) < 2:
            return {"error": "need equal-length arrays with at least 2 points"}
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
        den = sum((xs[i] - mx) ** 2 for i in range(n))
        if den == 0:
            return {"error": "all x values are the same"}
        slope = num / den
        intercept = my - slope * mx
        y_pred = [slope * xi + intercept for xi in xs]
        ss_res = sum((ys[i] - y_pred[i])**2 for i in range(n))
        ss_tot = sum((ys[i] - my)**2 for i in range(n))
        r2 = 1 - ss_res / ss_tot if ss_tot else 1.0
        return {"slope": round(slope, 6), "intercept": round(intercept, 6),
                "r2": round(r2, 6), "equation": f"y = {slope:.4f}x + {intercept:.4f}",
                "n_points": n}

    @tool(description="Confusion matrix visualization", category="viz")
    async def confusion_text_matrix(self, labels: list, true_labels: list,
                                     pred_labels: list) -> Dict:
        unique = sorted(set(true_labels) | set(pred_labels))
        matrix = {str(l): {str(p): 0 for p in unique} for l in unique}
        for t, p in zip(true_labels, pred_labels):
            matrix[str(t)][str(p)] = matrix[str(t)].get(str(p), 0) + 1
        
        lines = ["       " + "  ".join(f"{u:>5}" for u in unique)]
        lines.append("       " + "  ".join("-----" for _ in unique))
        for l in unique:
            row = f"{str(l):>5} |" + "  ".join(f"{matrix[str(l)][str(u)]:>5}" for u in unique)
            lines.append(row)
        return {"text_matrix": "\n".join(lines), "labels": unique, "total": len(true_labels)}
