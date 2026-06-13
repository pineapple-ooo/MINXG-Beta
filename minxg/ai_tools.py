"""
"""
from __future__ import annotations
from typing import Dict, List, Optional
import math
import re
from .base import BaseWorker, tool


class AiToolsWorker(BaseWorker):
    worker_id = "ai_tools"
    version = "1.0.0"

    @tool(description="Estimate token count", category="text")
    async def estimate_tokens(self, text: str, method: str = "char_div_4") -> Dict:
        if method == "char_div_4":
            tokens = max(1, len(text) // 4)
        elif method == "word_count":
            tokens = len(text.split())
        elif method == "char_div_3":
            tokens = max(1, len(text) // 3)
        else:
            tokens = max(1, len(text) // 4)
        return {"tokens_estimated": tokens, "method": method, "char_count": len(text)}

    @tool(description="Cosine similarity between texts", category="compare")
    async def text_similarity(self, a: str, b: str) -> Dict:
        def _vec(s: str) -> Dict[str, int]:
            d = {}
            for w in s.lower().split():
                d[w] = d.get(w, 0) + 1
            return d
        va, vb = _vec(a), _vec(b)
        keys = set(va) | set(vb)
        dot = sum(va.get(k, 0) * vb.get(k, 0) for k in keys)
        na = math.sqrt(sum(v * v for v in va.values()))
        nb = math.sqrt(sum(v * v for v in vb.values()))
        sim = dot / (na * nb) if na and nb else 0.0
        return {"similarity": round(sim, 6), "common_words": len(keys)}

    @tool(description="Split long text by token limit", category="text")
    async def chunk_text(self, text: str, max_tokens: int = 2000, overlap: int = 200) -> Dict:
        sentences = re.split(r'(?<=[.!?。！？\n])\s*', text)
        chunks, cur, cur_len = [], [], 0
        for s in sentences:
            sl = len(s) // 4
            if cur_len + sl > max_tokens and cur:
                chunks.append(" ".join(cur))
                overlap_txt = cur[-overlap:] if overlap else []
                cur = overlap_txt[:]
                cur_len = sum(len(t) // 4 for t in cur)
            cur.append(s)
            cur_len += sl
        if cur:
            chunks.append(" ".join(cur))
        return {"chunks": len(chunks), "texts": chunks}

    @tool(description="Extract text keywords (TF-IDF)", category="extract")
    async def extract_keywords(self, text: str, top_k: int = 10) -> Dict:
        words = re.findall(r'\w+', text.lower())
        freq: Dict[str, int] = {}
        for w in words:
            if len(w) > 2:
                freq[w] = freq.get(w, 0) + 1
        total = sum(freq.values()) or 1
        scored = [(w, c / total) for w, c in freq.items()]
        scored.sort(key=lambda x: -x[1])
        top = [{"word": w, "score": round(s, 6)} for w, s in scored[:top_k]]
        return {"keywords": top, "total_unique": len(freq)}

    @tool(description="Generate text summary", category="summarize")
    async def summarize_text(self, text: str, ratio: float = 0.3, min_sentences: int = 1) -> Dict:
        sentences = re.split(r'(?<=[.!?。！？])\s+', text.strip())
        if len(sentences) <= 3:
            return {"summary": text, "original_sentences": len(sentences)}
        words = [set(re.findall(r'\w+', s.lower())) for s in sentences]
        scores = [0.0] * len(sentences)
        for i in range(len(sentences)):
            for j in range(len(sentences)):
                if i != j and words[i] and words[j]:
                    scores[i] += len(words[i] & words[j]) / len(words[i] | words[j])
        ranked = sorted(range(len(sentences)), key=lambda i: -scores[i])
        keep = max(min_sentences, int(len(sentences) * ratio))
        selected = sorted(ranked[:keep])
        summary = " ".join(sentences[i] for i in selected)
        return {"summary": summary, "original_sentences": len(sentences), "kept": keep}

    @tool(description="Simple sentiment analysis", category="analyze")
    async def sentiment_analyze(self, text: str) -> Dict:
        positive = {"good", "great", "excellent", "amazing", "love", "wonderful"},
        negative = {"bad", "terrible", "awful", "hate", "poor", "worst", "ugly"}
        words = set(re.findall(r'\w+', text.lower()))
        pos = len(words & positive)
        neg = len(words & negative)
        if pos > neg:
            label, conf = "positive", pos / max(1, pos + neg)
        elif neg > pos:
            label, conf = "negative", neg / max(1, pos + neg)
        else:
            label, conf = "neutral", 0.5
        return {"sentiment": label, "confidence": round(conf, 4), "positive_hits": pos, "negative_hits": neg}

    @tool(description="Detect text language", category="detect")
    async def detect_language(self, text: str) -> Dict:
        patterns = {
            "zh": r'[\u4e00-\u9fff]',
            "ja": r'[\u3040-\u309f\u30a0-\u30ff]',
            "ko": r'[\uac00-\ud7af]',
            "ar": r'[\u0600-\u06ff]',
            "ru": r'[\u0400-\u04ff]',
            "th": r'[\u0e00-\u0e7f]',
        }
        scores = {}
        for lang, pat in patterns.items():
            cnt = len(re.findall(pat, text))
            if cnt:
                scores[lang] = cnt
        # English
        en = len(re.findall(r'[a-zA-Z]+', text))
        if en:
            scores["en"] = en
        if not scores:
            return {"language": "unknown", "confidence": 0.0}
        best = max(scores, key=scores.get)
        total = sum(scores.values())
        return {"language": best, "confidence": round(scores[best] / total, 4), "scores": scores}

    @tool(description="Fill template string with variables", category="fill")
    async def fill_template(self, template: str, variables: dict) -> Dict:
        try:
            result = template.format(**variables)
            return {"result": result, "missing_keys": []}
        except KeyError as e:
            return {"error": f"missing variable: {e}", "result": template}

    @tool(description="Compress context for long conversations", category="compress")
    async def compress_context(self, text: str, method: str = "dedup_lines") -> Dict:
        lines = text.split("\n")
        if method == "dedup_lines":
            seen, out = set(), []
            for line in lines:
                stripped = line.strip()
                if stripped and stripped not in seen:
                    seen.add(stripped)
                    out.append(line)
                elif not stripped:
                    out.append(line)
            result = "\n".join(out)
            ratio = len(result) / max(1, len(text))
        elif method == "strip_blank":
            result = "\n".join(l for l in lines if l.strip())
            ratio = len(result) / max(1, len(text))
        else:
            result = text
            ratio = 1.0
        return {"compressed": result, "ratio": round(ratio, 4), "original_chars": len(text), "compressed_chars": len(result)}

    @tool(description="Build few-shot prompt", category="prompt")
    async def build_few_shot(self, task: str, examples: list, query: str) -> Dict:
        for i, ex in enumerate(examples, 1):
            if isinstance(ex, dict):
                pass
            else:
                parts.append(f"{i}. {ex}")
        return {"prompt": "\n".join(parts), "examples_count": len(examples)}

    @tool(description="Build Chain-of-Thought prompt", category="prompt")
    async def build_cot_prompt(self, question: str, steps_hint: int = 3) -> Dict:
        prompt = (
            f"...\n"
        )
        return {"prompt": prompt, "steps_hint": steps_hint}

    @tool(description="Format conversion: markdown/plain/json", category="convert")
    async def convert_format(self, text: str, from_fmt: str, to_fmt: str) -> Dict:
        if from_fmt == "markdown" and to_fmt == "json":
            sections = re.split(r'(?:^|\n)(#{1,6})\s+(.+)$', text, flags=re.MULTILINE)
            return {"result": {"sections": len(sections), "text": text}}
        elif from_fmt == "json" and to_fmt == "markdown":
            import json
            try:
                data = json.loads(text)
                lines = []
                for k, v in data.items():
                    lines.append(f"## {k}\n{v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}\n")
                return {"result": "\n".join(lines)}
            except Exception as e:
                return {"error": str(e)}
        elif to_fmt == "plain":
            result = re.sub(r'[*_~`#]', '', text)
            return {"result": result}
        return {"result": text}

    @tool(description="Generate tool JSON Schema definition", category="schema")
    async def generate_tool_schema(self, name: str, description: str, params: dict) -> Dict:
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
        for pname, pdesc in params.items():
            ptype = "string"
            if "int" in str(pdesc).lower() or "number" in str(pdesc).lower():
                ptype = "number"
            elif "bool" in str(pdesc).lower():
                ptype = "boolean"
            schema["function"]["parameters"]["properties"][pname] = {
                "type": ptype, "description": str(pdesc)
            }
        return {"schema": schema}

    @tool(description="Validate LLM output for dangerous content", category="safety")
    async def safety_check(self, text: str) -> Dict:
        dangerous = [
            r'rm\s+-rf\s+/', r'drop\s+table', r'DELETE\s+FROM',
            r'eval\s*\(', r'exec\s*\(', r'__import__', r'subprocess',
        ]
        warnings = []
        for pat in dangerous:
            if re.search(pat, text, re.IGNORECASE):
                warnings.append(f"detected: {pat}")
        return {"safe": len(warnings) == 0, "warnings": warnings, "count": len(warnings)}

    @tool(description="Calculate recommended temperature", category="calc")
    async def recommend_temperature(self, task_type: str) -> Dict:
        mapping = {
            "code": 0.1, "math": 0.0, "translation": 0.2,
            "qa": 0.3, "summary": 0.4, "chat": 0.7,
            "creative": 0.9, "brainstorm": 1.0, "story": 1.2,
        }
        temp = mapping.get(task_type.lower(), 0.5)

    @tool(description="Suggest prompt length from text", category="calc")
    async def suggest_prompt_length(self, model_name: str) -> Dict:
        limits = {
            "gpt-4o": 128000, "gpt-4o-mini": 128000,
            "claude-sonnet": 200000, "claude-haiku": 200000,
            "gemini-pro": 32768, "deepseek-chat": 128000,
            "qwen-max": 32768, "glm-4": 128000,
            "llama3": 8192, "mistral": 32768,
        }
        limit = 8192
        for k, v in limits.items():
            if k in model_name.lower():
                limit = v
                break
        safe = int(limit * 0.75)
        return {"model": model_name, "max_tokens": limit, "recommended_input": safe}

    @tool(description="Simulate LLM token budget calculation", category="calc")
    async def token_budget(self, system_prompt: str, user_input: str, output_tokens: int = 1024) -> Dict:
        sys_tok = len(system_prompt) // 4
        usr_tok = len(user_input) // 4
        total = sys_tok + usr_tok + output_tokens
        return {
            "system_tokens": sys_tok, "user_tokens": usr_tok,
            "output_tokens": output_tokens, "total_budget": total
        }

    @tool
    async def text_to_speech_estimate(self, text: str = "") -> dict:
        """Estimate TTS duration/cost for a given text."""
        words = len(text.split())
        chars = len(text)
        estimated_duration_s = words * 0.35
        return {"words": words, "chars": chars, "estimated_seconds": round(estimated_duration_s, 1)}

    @tool
    async def prompt_optimize(self, prompt: str = "", goal: str = "clarity") -> dict:
        """Suggest improvements for an LLM prompt."""
        suggestions = []
        if len(prompt) < 20:
            suggestions.append("Prompt is very short. Consider adding context.")
        if "please" not in prompt.lower():
            suggestions.append("Consider adding politeness markers.")
        if "?" not in prompt and goal == "question":
            suggestions.append("Add a clear question or instruction.")
        return {"original_length": len(prompt), "suggestions": suggestions, "goal": goal}
