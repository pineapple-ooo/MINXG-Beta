"""Knowledge base — see __init__.py."""
from typing import List, Dict, Any

class KnowledgeBase:
    def __init__(self):
        self._docs: Dict[str, str] = {}
    def add_document(self, doc_id, content):
        self._docs[doc_id] = content
    def search(self, query, k=5):
        q = set(query.lower().split())
        scored = []
        for did, content in self._docs.items():
            d = set(content.lower().split())
            if q and d:
                score = len(q & d) / len(q | d)
                if score > 0:
                    scored.append({"id": did, "content": content, "score": score})
        scored.sort(key=lambda x: -x["score"])
        return scored[:k]

_kb = KnowledgeBase()
add_document = _kb.add_document
search = _kb.search
