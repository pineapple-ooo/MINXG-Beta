"""
text_adv.py — Advanced Text Processing Operators 

80+ operators: regex, comparison/diff, normalization, tokenization,
template, fuzzy, encoding/charset. IDs: 5000-5699.
All pure stdlib. No external deps.
"""

from __future__ import annotations
import re
import base64
import codecs
import urllib.parse
import html
import xml.sax.saxutils as saxutils
from typing import Dict, List, Any, Tuple
from minxg.base import BaseWorker, tool


class TextAdvWorker(BaseWorker):
    worker_id = "text_adv"
    version = "0.16.0"

    # ══════════════════════════════════════════════════════════════════════════
    # REGEX OPERATIONS (IDs 5000-5099)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Full regex match (anchored)", category="regex")
    async def regex_match(self, pattern: str, text: str) -> Dict:
        try:
            m = re.fullmatch(pattern, text)
            return {"matched": m is not None, "match": m.group() if m else None, "pattern": pattern}
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    @tool(description="Regex search (first match)", category="regex")
    async def regex_search(self, pattern: str, text: str) -> Dict:
        try:
            m = re.search(pattern, text)
            return {
                "found": m is not None,
                "match": m.group() if m else None,
                "start": m.start() if m else None,
                "end": m.end() if m else None,
                "pattern": pattern,
            }
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    @tool(description="Find all regex matches", category="regex")
    async def regex_findall(self, pattern: str, text: str) -> Dict:
        try:
            matches = re.findall(pattern, text)
            return {"matches": matches, "count": len(matches), "pattern": pattern}
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    @tool(description="Replace all regex matches", category="regex")
    async def regex_replace(self, pattern: str, text: str, replacement: str) -> Dict:
        try:
            result = re.sub(pattern, replacement, text)
            count = len(re.findall(pattern, text))
            return {"result": result, "count": count, "pattern": pattern}
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    @tool(description="Split text by regex pattern", category="regex")
    async def regex_split(self, pattern: str, text: str) -> Dict:
        try:
            parts = re.split(pattern, text)
            return {"parts": parts, "count": len(parts), "pattern": pattern}
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    @tool(description="Get regex groups from first match", category="regex")
    async def regex_groups(self, pattern: str, text: str) -> Dict:
        try:
            m = re.search(pattern, text)
            if not m: return {"found": False, "groups": [], "pattern": pattern}
            return {"found": True, "groups": list(m.groups()), "group_dict": m.groupdict(), "pattern": pattern}
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    @tool(description="Get named groups from regex", category="regex")
    async def regex_named_groups(self, pattern: str, text: str) -> Dict:
        try:
            m = re.search(pattern, text)
            if not m: return {"found": False, "named_groups": {}, "pattern": pattern}
            return {"found": True, "named_groups": m.groupdict(), "pattern": pattern}
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    @tool(description="Validate regex pattern (check syntax)", category="regex")
    async def regex_is_valid(self, pattern: str) -> Dict:
        try:
            re.compile(pattern)
            return {"valid": True, "pattern": pattern}
        except re.error as e:
            return {"valid": False, "error": str(e), "pattern": pattern}

    @tool(description="Escape special regex characters in text", category="regex")
    async def regex_escape(self, text: str) -> Dict:
        return {"result": re.escape(text), "input": text}

    @tool(description="Count regex pattern occurrences", category="regex")
    async def regex_pattern_count(self, pattern: str, text: str) -> Dict:
        try:
            count = len(re.findall(pattern, text))
            return {"count": count, "pattern": pattern}
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    @tool(description="Find all start/end positions of pattern matches", category="regex")
    async def regex_pattern_positions(self, pattern: str, text: str) -> Dict:
        try:
            positions = [(m.start(), m.end(), m.group()) for m in re.finditer(pattern, text)]
            return {"matches": positions, "count": len(positions), "pattern": pattern}
        except re.error as e:
            return {"error": str(e), "pattern": pattern}

    # ══════════════════════════════════════════════════════════════════════════
    # TEXT COMPARISON & DIFF (IDs 5100-5199)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Levenshtein edit distance", category="comparison")
    async def levenshtein_distance(self, a: str, b: str) -> Dict:
        if len(a) < len(b):
            return self.levenshtein_distance(b, a)
        if len(b) == 0:
            return {"result": len(a), "a": a, "b": b}
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                curr.append(min(prev[j+1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
            prev = curr
        return {"result": prev[-1], "a": a, "b": b}

    @tool(description="Damerau-Levenshtein distance (adjacent transpositions allowed)", category="comparison")
    async def damerau_levenshtein(self, a: str, b: str) -> Dict:
        m, n = len(a), len(b)
        d = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1): d[i][0] = i
        for j in range(n + 1): d[0][j] = j
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                cost = 0 if a[i-1] == b[j-1] else 1
                d[i][j] = min(d[i-1][j] + 1, d[i][j-1] + 1, d[i-1][j-1] + cost)
                if i > 1 and j > 1 and a[i-1] == b[j-2] and a[i-2] == b[j-1]:
                    d[i][j] = min(d[i][j], d[i-2][j-2] + cost)
        return {"result": d[m][n], "a": a, "b": b}

    @tool(description="Jaro-Winkler similarity (0-1, higher = more similar)", category="comparison")
    async def jaro_winkler_similarity(self, a: str, b: str) -> Dict:
        if a == b: return {"result": 1.0, "a": a, "b": b}
        len_a, len_b = len(a), len(b)
        if len_a == 0 or len_b == 0: return {"result": 0.0, "a": a, "b": b}
        match_dist = max(len_a, len_b) // 2 - 1
        if match_dist < 0: match_dist = 0
        a_matches = [False] * len_a
        b_matches = [False] * len_b
        matches = 0
        transpositions = 0
        for i in range(len_a):
            start = max(0, i - match_dist)
            end = min(i + match_dist + 1, len_b)
            for j in range(start, end):
                if b_matches[j] or a[i] != b[j]: continue
                a_matches[i] = True
                b_matches[j] = True
                matches += 1
                break
        if matches == 0: return {"result": 0.0, "a": a, "b": b}
        k = 0
        for i in range(len_a):
            if not a_matches[i]: continue
            while not b_matches[k]: k += 1
            if a[i] != b[k]: transpositions += 1
            k += 1
        jaro = (matches/len_a + matches/len_b + (matches - transpositions/2)/matches) / 3
        prefix = 0
        for i in range(min(4, min(len_a, len_b))):
            if a[i] == b[i]: prefix += 1
            else: break
        return {"result": jaro + prefix * 0.1 * (1 - jaro), "a": a, "b": b}

    @tool(description="Jaccard similarity of character n-grams (0-1)", category="comparison")
    async def jaccard_similarity(self, a: str, b: str, n: int = 2) -> Dict:
        def ngrams(s, n):
            return set(s[i:i+n] for i in range(max(0, len(s) - n + 1)))
        if not a or not b: return {"result": 0.0, "a": a, "b": b}
        g1, g2 = ngrams(a, n), ngrams(b, n)
        inter = len(g1 & g2)
        union = len(g1 | g2)
        return {"result": inter / union if union else 0.0, "ngram_size": n, "a": a[:50], "b": b[:50]}

    @tool(description="Cosine similarity of n-gram vectors (0-1)", category="comparison")
    async def cosine_similarity_ngrams(self, a: str, b: str, n: int = 2) -> Dict:
        def ngrams(s, n):
            return {ng: s[i:i+n].count(ng) for i in range(max(0, len(s)-n+1)) for ng in [s[i:i+n]]}
        if not a or not b: return {"result": 0.0}
        ng_a = ngrams(a, n)
        ng_b = ngrams(b, n)
        all_keys = set(ng_a) | set(ng_b)
        dot = sum(ng_a.get(k, 0) * ng_b.get(k, 0) for k in all_keys)
        mag_a = math.sqrt(sum(v*v for v in ng_a.values()))
        mag_b = math.sqrt(sum(v*v for v in ng_b.values()))
        if mag_a == 0 or mag_b == 0: return {"result": 0.0}
        return {"result": dot / (mag_a * mag_b), "ngram_size": n}

    @tool(description="Hamming distance (same-length strings only)", category="comparison")
    async def hamming_distance(self, a: str, b: str) -> Dict:
        if len(a) != len(b): return {"error": "strings must be equal length", "a": a, "b": b}
        return {"result": sum(ca != cb for ca, cb in zip(a, b)), "a": a, "b": b}

    @tool(description="Longest common substring", category="comparison")
    async def longest_common_substring(self, a: str, b: str) -> Dict:
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(2)]
        max_len = 0
        end_pos = 0
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i-1] == b[j-1]:
                    dp[i % 2][j] = dp[(i-1) % 2][j-1] + 1
                    if dp[i % 2][j] > max_len:
                        max_len = dp[i % 2][j]
                        end_pos = i
                else:
                    dp[i % 2][j] = 0
        return {"result": a[end_pos - max_len:end_pos], "length": max_len, "a": a, "b": b}

    @tool(description="Longest common subsequence", category="comparison")
    async def longest_common_subsequence(self, a: str, b: str) -> Dict:
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i-1] == b[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        # Backtrack
        lcs = []
        i, j = m, n
        while i > 0 and j > 0:
            if a[i-1] == b[j-1]:
                lcs.append(a[i-1])
                i -= 1; j -= 1
            elif dp[i-1][j] > dp[i][j-1]:
                i -= 1
            else:
                j -= 1
        return {"result": "".join(reversed(lcs)), "length": dp[m][n], "a": a, "b": b}

    @tool(description="Full diff with operations (insert/delete/equal)", category="comparison")
    async def myers_diff(self, a: str, b: str) -> Dict:
        # Simple LCS-based diff
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i-1] == b[j-1]: dp[i][j] = dp[i-1][j-1] + 1
                else: dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        ops = []
        i, j = m, n
        while i > 0 or j > 0:
            if i > 0 and j > 0 and a[i-1] == b[j-1]:
                ops.append(("equal", a[i-1]))
                i -= 1; j -= 1
            elif i > 0 and (j == 0 or dp[i-1][j] >= dp[i][j-1]):
                ops.append(("delete", a[i-1]))
                i -= 1
            else:
                ops.append(("insert", b[j-1]))
                j -= 1
        ops.reverse()
        added = sum(1 for op, _ in ops if op == "insert")
        deleted = sum(1 for op, _ in ops if op == "delete")
        return {"ops": ops, "added": added, "deleted": deleted, "equal": len(ops) - added - deleted}

    @tool(description="Diff statistics summary", category="comparison")
    async def diff_stats(self, a: str, b: str) -> Dict:
        diff = await self.myers_diff(a, b)
        return {
            "total_changes": diff["added"] + diff["deleted"],
            "added": diff["added"],
            "deleted": diff["deleted"],
            "similarity": round((diff["equal"] / max(1, len(a) + len(b))) * 100, 1),
        }

    @tool(description="Overall similarity ratio 0-100", category="comparison")
    async def similarity_ratio(self, a: str, b: str) -> Dict:
        d = await self.levenshtein_distance(a, b)
        max_len = max(len(a), len(b))
        ratio = (1 - d["result"] / max_len) * 100 if max_len > 0 else 100
        return {"result": round(ratio, 2), "a": a, "b": b}

    @tool(description="Check if two strings are anagrams", category="comparison")
    async def is_anagram(self, a: str, b: str) -> Dict:
        norm = lambda s: sorted(s.lower().replace(" ", ""))
        return {"result": norm(a) == norm(b), "a": a, "b": b}

    @tool(description="Group words that are anagrams of each other", category="comparison")
    async def anagram_groups(self, words: List[str]) -> Dict:
        groups = {}
        for w in words:
            key = tuple(sorted(w.lower()))
            groups.setdefault(key, []).append(w)
        return {"groups": list(groups.values()), "count": len(groups)}

    # ══════════════════════════════════════════════════════════════════════════
    # TEXT NORMALIZATION (IDs 5200-5299)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Unicode normalization (NFD, NFC, NFKC, NFKD)", category="normalization")
    async def normalize_unicode(self, text: str, form: str = "NFC") -> Dict:
        import unicodedata
        valid_forms = {"NFD", "NFC", "NFKD", "NFKC"}
        if form not in valid_forms:
            return {"error": f"form must be one of {valid_forms}", "input": text}
        return {"result": unicodedata.normalize(form, text), "form": form, "input": text[:100]}

    @tool(description="Unicode character category", category="normalization")
    async def unicode_category(self, text: str) -> Dict:
        import unicodedata
        cats = [(ch, unicodedata.category(ch), unicodedata.name(ch, "UNKNOWN")) for ch in text[:50]]
        return {"categories": cats[:20]}

    @tool(description="Remove accents/diacritics from text", category="normalization")
    async def remove_accents(self, text: str) -> Dict:
        import unicodedata
        nfd = unicodedata.normalize("NFD", text)
        return {"result": "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")}

    @tool(description="Normalize whitespace (collapse multiple spaces)", category="normalization")
    async def normalize_whitespace(self, text: str) -> Dict:
        return {"result": re.sub(r'\s+', ' ', text), "input": text[:100]}

    @tool(description="Collapse multiple whitespace to single space, trim lines", category="normalization")
    async def collapse_whitespace(self, text: str) -> Dict:
        lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
        return {"result": "\n".join(line for line in lines if line)}

    @tool(description="Casefold normalization (for case-insensitive comparison)", category="normalization")
    async def normalize_casefold(self, text: str) -> Dict:
        return {"result": text.casefold(), "input": text[:100]}

    @tool(description="Remove all whitespace characters", category="normalization")
    async def strip_all_whitespace(self, text: str) -> Dict:
        return {"result": re.sub(r'\s+', '', text), "input": text[:100]}

    @tool(description="Remove empty lines, keep content lines", category="normalization")
    async def squash_empty_lines(self, text: str) -> Dict:
        return {"result": re.sub(r'\n\s*\n', '\n', text).strip()}

    @tool(description="Trim leading/trailing whitespace from each line", category="normalization")
    async def trim_lines(self, text: str) -> Dict:
        return {"result": "\n".join(line.strip() for line in text.splitlines())}

    @tool(description="Remove diacritics using decomposition", category="normalization")
    async def remove_diacritics(self, text: str) -> Dict:
        import unicodedata
        return {"result": "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")}

    # ══════════════════════════════════════════════════════════════════════════
    # TOKENIZATION & PARSING (IDs 5300-5399)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Split text into words (whitespace + punctuation)", category="tokenization")
    async def word_tokenize(self, text: str) -> Dict:
        tokens = re.findall(r"\b\w+\b", text)
        return {"tokens": tokens, "count": len(tokens)}

    @tool(description="Split text into sentences (period/exclamation/question aware)", category="tokenization")
    async def sentence_tokenize(self, text: str) -> Dict:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return {"sentences": [s for s in sentences if s.strip()], "count": len(sentences)}

    @tool(description="Split text into paragraphs", category="tokenization")
    async def paragraph_tokenize(self, text: str) -> Dict:
        paras = re.split(r'\n\s*\n', text)
        return {"paragraphs": [p.strip() for p in paras if p.strip()], "count": len(paras)}

    @tool(description="Generate character n-grams", category="tokenization")
    async def char_ngrams(self, text: str, n: int = 3) -> Dict:
        if len(text) < n: return {"ngrams": [], "count": 0}
        ngrams_list = [text[i:i+n] for i in range(len(text) - n + 1)]
        return {"ngrams": ngrams_list, "count": len(ngrams_list), "n": n}

    @tool(description="Generate word n-grams", category="tokenization")
    async def word_ngrams(self, text: str, n: int = 2) -> Dict:
        words = re.findall(r'\b\w+\b', text.lower())
        if len(words) < n: return {"ngrams": [], "count": 0}
        ngrams_list = [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]
        return {"ngrams": ngrams_list, "count": len(ngrams_list), "n": n}

    @tool(description="Token frequency counts", category="tokenization")
    async def token_frequency(self, text: str, top_n: int = 20) -> Dict:
        tokens = re.findall(r'\b\w{2,}\b', text.lower())
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        sorted_freq = sorted(freq.items(), key=lambda x: -x[1])[:top_n]
        return {"frequencies": sorted_freq, "total_unique": len(freq)}

    @tool(description="Top-k most frequent tokens", category="tokenization")
    async def top_k_tokens(self, text: str, k: int = 10) -> Dict:
        result = await self.token_frequency(text, top_n=k)
        return {"top_tokens": result["frequencies"][:k]}

    @tool(description="Vocabulary size (unique tokens)", category="tokenization")
    async def vocabulary_size(self, text: str) -> Dict:
        tokens = set(re.findall(r'\b\w+\b', text.lower()))
        return {"result": len(tokens), "sample": list(tokens)[:20]}

    @tool(description="Split camelCase into words", category="tokenization")
    async def split_camelcase(self, text: str) -> Dict:
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W)|[A-Z]+', text)
        return {"result": words, "original": text}

    @tool(description="Split snake_case into words", category="tokenization")
    async def split_snakecase(self, text: str) -> Dict:
        return {"result": text.replace('_', ' ').split(), "original": text}

    @tool(description="Convert snake_case to camelCase", category="tokenization")
    async def unsnakecase(self, text: str) -> Dict:
        parts = text.split('_')
        return {"result": parts[0] + ''.join(p.capitalize() for p in parts[1:]), "input": text}

    @tool(description="Extract content between delimiters (first match)", category="tokenization")
    async def extract_between(self, text: str, start: str, end: str) -> Dict:
        m = re.search(re.escape(start) + r'(.*?)' + re.escape(end), text)
        return {"result": m.group(1) if m else None, "input": text[:50]}

    @tool(description="Strip HTML/XML tags", category="tokenization")
    async def tag_strip(self, text: str) -> Dict:
        return {"result": re.sub(r'<[^>]+>', '', text), "input": text[:50]}

    @tool(description="Extract all hashtags from text", category="tokenization")
    async def extract_hashtags(self, text: str) -> Dict:
        tags = re.findall(r'#(\w+)', text)
        return {"hashtags": tags, "count": len(tags)}

    @tool(description="Extract all @mentions from text", category="tokenization")
    async def extract_mentions(self, text: str) -> Dict:
        mentions = re.findall(r'@(\w+)', text)
        return {"mentions": mentions, "count": len(mentions)}

    @tool(description="Extract all URLs from text", category="tokenization")
    async def extract_urls(self, text: str) -> Dict:
        urls = re.findall(r'https?://\S+', text)
        return {"urls": urls, "count": len(urls)}

    @tool(description="Extract all email addresses", category="tokenization")
    async def extract_emails(self, text: str) -> Dict:
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
        return {"emails": emails, "count": len(emails)}

    @tool(description="Extract numbers from text", category="tokenization")
    async def extract_numbers(self, text: str) -> Dict:
        nums = re.findall(r'-?\d+\.?\d*', text)
        return {"numbers": [float(n) if '.' in n else int(n) for n in nums[:50]], "count": len(nums)}

    @tool(description="Soundex phonetic encoding", category="tokenization")
    async def phonetic_encode(self, text: str) -> Dict:
        word = text.upper()[:1]
        soundex_map = {'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3', 'L': '4', 'MN': '5', 'R': '6', 'HWY': '0', 'AEIOU': '0'}
        rest = text.upper()[1:]
        for char in rest:
            for key, val in soundex_map.items():
                if char in key:
                    if val != '0' and val != word[-1]:
                        word += val
                    break
        word = word[:4].ljust(4, '0')
        return {"soundex": word, "input": text, "metaphone": self._metaphone(text.upper())}

    def _metaphone(self, text: str) -> str:
        # Simplified metaphone
        if not text: return ""
        result = []
        vowels = set("AEIOU")
        if text[0] in "GKP": result.append(text[0])
        for i, c in enumerate(text):
            if c in vowels:
                if not result or result[-1] != 'A':
                    result.append('A')
            elif c == 'F': result.append('F')
            elif c == 'S': result.append('S')
            elif c == 'J': result.append('J')
            elif c == 'T':
                if i+1 < len(text) and text[i+1] in 'IOU': result.append('J')
                else: result.append('T')
            elif c == 'K' and (not result or result[-1] != 'K'): result.append('K')
            elif c == 'R': result.append('R')
        return ''.join(result[:4]).ljust(4, '0')

    # ══════════════════════════════════════════════════════════════════════════
    # TEMPLATE & FORMATTING (IDs 5400-5499)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Render ${var} style template", category="template")
    async def template_render(self, template: str, vars: Dict[str, str]) -> Dict:
        result = template
        for k, v in vars.items():
            result = result.replace(f"${{{k}}}", str(v))
            result = result.replace(f"${k}", str(v))
        return {"result": result, "template": template[:100]}

    @tool(description="Render %(name)s Python-style template", category="template")
    async def template_render_python(self, template: str, vars: Dict[str, str]) -> Dict:
        try:
            result = template % vars
            return {"result": result, "template": template[:100]}
        except Exception as e:
            return {"error": str(e), "template": template[:100]}

    @tool(description="Truncate text at word boundary to max length", category="template")
    async def truncate_words(self, text: str, max_len: int = 100) -> Dict:
        if len(text) <= max_len: return {"result": text, "truncated": False}
        truncated = text[:max_len]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        return {"result": truncated + "…", "truncated": True, "original_length": len(text)}

    @tool(description="Truncate at sentence boundary", category="template")
    async def truncate_sentences(self, text: str, max_sentences: int = 2) -> Dict:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        result = ' '.join(sentences[:max_sentences])
        return {"result": result, "truncated": len(sentences) > max_sentences}

    @tool(description="Word wrap text at given width", category="template")
    async def word_wrap(self, text: str, width: int = 80) -> Dict:
        words = text.split()
        lines, line = [], ""
        for word in words:
            if len(line) + len(word) + 1 <= width:
                line = (line + " " + word).strip()
            else:
                if line: lines.append(line)
                line = word
        if line: lines.append(line)
        return {"result": "\n".join(lines), "lines": len(lines)}

    @tool(description="Indent each line by n spaces", category="template")
    async def indent_lines(self, text: str, n: int = 2) -> Dict:
        prefix = " " * n
        return {"result": "\n".join(prefix + line for line in text.splitlines()), "spaces": n}

    @tool(description="Center text within width", category="template")
    async def center_text(self, text: str, width: int = 80) -> Dict:
        return {"result": text.center(width), "width": width}

    @tool(description="Markdown table from list of dicts", category="template")
    async def table_format(self, rows: List[Dict], cols: List[str] = None) -> Dict:
        if not rows: return {"result": ""}
        if cols is None: cols = list(rows[0].keys())
        header = "| " + " | ".join(cols) + " |"
        separator = "| " + " | ".join("-" * len(c) for c in cols) + " |"
        data_rows = []
        for row in rows:
            data_rows.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
        result = "\n".join([header, separator] + data_rows)
        return {"result": result, "rows": len(rows), "cols": cols}

    @tool(description="Escape text for JSON string", category="template")
    async def json_escape(self, text: str) -> Dict:
        return {"result": json.dumps(text)[1:-1], "input": text[:50]}

    @tool(description="Escape text for XML/HTML", category="template")
    async def xml_escape(self, text: str) -> Dict:
        return {"result": saxutils.escape(text), "input": text[:50]}

    @tool(description="Escape text for HTML", category="template")
    async def html_escape(self, text: str) -> Dict:
        return {"result": html.escape(text), "input": text[:50]}

    @tool(description="Escape text for SQL LIKE clause", category="template")
    async def sql_escape(self, text: str) -> Dict:
        return {"result": text.replace("'", "''").replace("\\", "\\\\"), "input": text[:50]}

    @tool(description="camelCase to snake_case", category="template")
    async def camel_to_snake(self, text: str) -> Dict:
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
        return {"result": re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower(), "input": text}

    @tool(description="snake_case to camelCase", category="template")
    async def snake_to_camel(self, text: str) -> Dict:
        parts = text.split('_')
        return {"result": parts[0] + ''.join(p.capitalize() for p in parts[1:]), "input": text}

    @tool(description="kebab-case to snake_case", category="template")
    async def kebab_to_snake(self, text: str) -> Dict:
        return {"result": text.replace('-', '_'), "input": text}

    # ══════════════════════════════════════════════════════════════════════════
    # FUZZY & PATTERN (IDs 5500-5599)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Fuzzy match score (Levenshtein-based, normalized)", category="fuzzy")
    async def fuzzy_match_score(self, pattern: str, text: str) -> Dict:
        d = await self.levenshtein_distance(pattern.lower(), text.lower())
        max_len = max(len(pattern), len(text))
        score = max(0, (max_len - d["result"]) / max_len) * 100
        return {"result": round(score, 2), "distance": d["result"], "pattern": pattern, "text": text[:50]}

    @tool(description="Find best fuzzy match from list", category="fuzzy")
    async def fuzzy_best_match(self, pattern: str, choices: List[str]) -> Dict:
        if not choices: return {"result": None, "error": "empty list"}
        scored = []
        for c in choices:
            s = await self.fuzzy_match_score(pattern, c)
            scored.append((s["result"], c))
        scored.sort(key=lambda x: -x[0])
        best_score, best_choice = scored[0]
        return {"result": best_choice, "score": best_score, "all_scores": scored[:5]}

    @tool(description="Extract all occurrences of pattern", category="fuzzy")
    async def extract_pattern_all(self, pattern: str, text: str) -> Dict:
        matches = re.findall(pattern, text)
        return {"matches": matches, "count": len(matches), "pattern": pattern}

    @tool(description="Replace text between delimiters", category="fuzzy")
    async def replace_between(self, text: str, start: str, end: str, replacement: str) -> Dict:
        def replacer(m):
            return start + replacement + end
        result = re.sub(re.escape(start) + r'.*?' + re.escape(end), replacer, text)
        count = len(re.findall(re.escape(start) + r'.*?' + re.escape(end), text))
        return {"result": result, "replacements": count}

    @tool(description="Remove pattern from text", category="fuzzy")
    async def remove_pattern(self, pattern: str, text: str) -> Dict:
        result = re.sub(pattern, '', text)
        return {"result": result, "count": len(re.findall(pattern, text))}

    @tool(description="Check if string is pangram (contains all letters a-z)", category="fuzzy")
    async def is_pangram(self, text: str) -> Dict:
        letters = set(text.lower().replace(" ", ""))
        alphabet = set("abcdefghijklmnopqrstuvwxyz")
        return {"result": letters >= alphabet, "missing": list(alphabet - letters)}

    @tool(description="Check if string is heterogram (no repeated letters)", category="fuzzy")
    async def is_heterogram(self, text: str) -> Dict:
        letters = [c for c in text.lower() if c.isalpha()]
        return {"result": len(letters) == len(set(letters)), "input": text[:50]}

    @tool(description="Character frequency map", category="fuzzy")
    async def char_frequency(self, text: str) -> Dict:
        freq = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        return {"frequencies": dict(sorted(freq.items(), key=lambda x: -x[1])[:30])}

    @tool(description="Bigram frequency map", category="fuzzy")
    async def bigram_frequency(self, text: str) -> Dict:
        bg = [text[i:i+2] for i in range(len(text)-1)]
        freq = {}
        for b in bg:
            freq[b] = freq.get(b, 0) + 1
        return {"frequencies": dict(sorted(freq.items(), key=lambda x: -x[1])[:20])}

    # ══════════════════════════════════════════════════════════════════════════
    # ENCODING & CHARSETS (IDs 5600-5699)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="ROT13 cipher (letter substitution)", category="encoding")
    async def rot13(self, text: str) -> Dict:
        result = codecs.encode(text, 'rot_13')
        return {"result": result, "input": text[:50]}

    @tool(description="ROT47 cipher (full ASCII rotation)", category="encoding")
    async def rot47(self, text: str) -> Dict:
        def rot47_char(c):
            if 33 <= ord(c) <= 126:
                return chr(33 + ((ord(c) - 33 + 47) % 94))
            return c
        result = ''.join(rot47_char(c) for c in text)
        return {"result": result, "input": text[:50]}

    @tool(description="Caesar cipher with given shift", category="encoding")
    async def caesar_cipher(self, text: str, shift: int = 3) -> Dict:
        def shift_char(c):
            if 'a' <= c <= 'z': return chr((ord(c) - ord('a') + shift) % 26 + ord('a'))
            if 'A' <= c <= 'Z': return chr((ord(c) - ord('A') + shift) % 26 + ord('A'))
            return c
        return {"result": ''.join(shift_char(c) for c in text), "shift": shift}

    @tool(description="Vigenere cipher encode/decode", category="encoding")
    async def vigenere_cipher(self, text: str, key: str, decode: bool = False) -> Dict:
        if not key.isalpha(): return {"error": "key must be alphabetic"}
        key_seq = [ord(k.upper()) - ord('A') for k in key]
        result = []
        ki = 0
        for c in text:
            if c.isalpha():
                base = ord('A') if c.isupper() else ord('a')
                shift = -key_seq[ki % len(key_seq)] if decode else key_seq[ki % len(key_seq)]
                result.append(chr((ord(c) - base + shift) % 26 + base))
                ki += 1
            else:
                result.append(c)
        return {"result": ''.join(result), "key": key}

    @tool(description="Atbash cipher (reverse alphabet)", category="encoding")
    async def atbash(self, text: str) -> Dict:
        def atbash_char(c):
            if 'a' <= c <= 'z': return chr(ord('z') - (ord(c) - ord('a')))
            if 'A' <= c <= 'Z': return chr(ord('Z') - (ord(c) - ord('A')))
            return c
        return {"result": ''.join(atbash_char(c) for c in text), "input": text[:50]}

    @tool(description="Base16 (hex) encode", category="encoding")
    async def base16_encode(self, data: str) -> Dict:
        return {"result": data.encode().hex(), "input": data[:50]}

    @tool(description="Base16 (hex) decode", category="encoding")
    async def base16_decode(self, encoded: str) -> Dict:
        try:
            return {"result": bytes.fromhex(encoded).decode('utf-8', errors='replace')}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Base32 encode", category="encoding")
    async def base32_encode(self, data: str) -> Dict:
        return {"result": base64.b32encode(data.encode()).decode()}

    @tool(description="Base32 decode", category="encoding")
    async def base32_decode(self, encoded: str) -> Dict:
        try:
            return {"result": base64.b32decode(encoded).decode('utf-8', errors='replace')}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Simple ASCII block letter rendering", category="encoding")
    async def ascii_art(self, text: str) -> Dict:
        # Very simple block letters
        patterns = {
            'A': [" AAA ", "A   A", "AAAAA", "A   A", "A   A"],
            'B': ["BBBB ", "B   B", "BBBB ", "B   B", "BBBB "],
            'C': [" CCC ", "C   C", "C    ", "C   C", " CCC "],
            'D': ["DDD  ", "D  D ", "D   D ", "D  D ", "DDD  "],
            'E': ["EEEEE", "E    ", "EEE  ", "E    ", "EEEEE"],
            'F': ["FFFFF", "F    ", "FFF  ", "F    ", "F    "],
            'G': [" GGG ", "G    ", "G  GG", "G   G", " GGG "],
            'H': ["H   H", "H    ", "HHHHH", "H   H", "H   H"],
            'I': ["IIIII", "  I  ", "  I  ", "  I  ", "IIIII"],
            'J': ["JJJJJ", "   J ", "   J ", "J  J ", " JJ  "],
            'K': ["K   K", "K  K ", "KK   ", "K  K ", "K   K"],
            'L': ["L    ", "L    ", "L    ", "L    ", "LLLLL"],
            'M': ["M   M", "MM MM", "M M M", "M   M", "M   M"],
            'N': ["N   N", "NN  N", "N N N", "N  NN", "N   N"],
            'O': [" OOO ", "O   O", "O   O", "O   O", " OOO "],
            'P': ["PPPP ", "P   P", "PPPP ", "P    ", "P    "],
            'Q': [" QQQ ", "Q   Q", "Q Q Q", "Q  Q ", " QQ Q"],
            'R': ["RRRR ", "R   R", "RRRR ", "R  R ", "R   R"],
            'S': [" SSS ", "S    ", " SSS ", "    S", " SSS "],
            'T': ["TTTTT", "  T  ", "  T  ", "  T  ", "  T  "],
            'U': ["U   U", "U   U", "U   U", "U   U", " UUU "],
            'V': ["V   V", "V   V", "V   V", " V V ", "  V  "],
            'W': ["W   W", "W   W", "W W W", "WW WW", "W   W"],
            'X': ["X   X", " X X ", "  X  ", " X X ", "X   X"],
            'Y': ["Y   Y", " Y Y ", "  Y  ", "  Y  ", "  Y  "],
            'Z': ["ZZZZZ", "   Z ", "  Z  ", " Z   ", "ZZZZZ"],
            '0': [" 000 ", "0   0", "0   0", "0   0", " 000 "],
            '1': ["  1  ", " 11  ", "  1  ", "  1  ", "11111"],
            '2': [" 222 ", "2   2", "  22 ", " 2   ", "22222"],
            '3': ["3333 ", "    3", " 333 ", "    3", "3333 "],
            '4': ["4   4", "4   4", "44444", "    4", "    4"],
            '5': ["55555", "5    ", "5555 ", "    5", "5555 "],
            '6': [" 666 ", "6    ", "6666 ", "6   6", " 666 "],
            '7': ["77777", "    7", "   7 ", "   7 ", "   7 "],
            '8': [" 888 ", "8   8", " 888 ", "8   8", " 888 "],
            '9': [" 999 ", "9   9", " 9999", "    9", " 999 "],
            ' ': ["     ", "     ", "     ", "     ", "     "],
        }
        chars = [patterns.get(c.upper(), patterns[' ']) for c in text.upper()[:20]]
        lines = ["  ".join(chars[i] for chars in zip(*[patterns.get(c.upper(), patterns[' ']) for c in text.upper()[:20]])) for i in range(5)]
        return {"result": "\n".join(lines), "input": text}

    @tool(description="Word count statistics (words, chars, lines, avg word len)", category="encoding")
    async def word_count_stats(self, text: str) -> Dict:
        words = text.split()
        lines = text.splitlines()
        return {
            "words": len(words),
            "chars": len(text),
            "lines": len(lines),
            "avg_word_length": round(sum(len(w) for w in words) / max(1, len(words)), 2),
            "unique_words": len(set(words)),
        }


# Need math for cosine_similarity
import math