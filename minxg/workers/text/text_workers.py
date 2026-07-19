"""
MINXG Text Workers — Text processing and NLP tools.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional


class TextProcessWorker:
    """Basic text processing."""
    worker_id = "text_process"
    version = "0.19.0"

    def execute(self, text: str, operation: str = "word_count") -> Dict[str, Any]:
        if operation == "word_count":
            return {"text_length": len(text), "word_count": len(text.split()), "line_count": text.count("\n") + 1}
        elif operation == "uppercase":
            return {"result": text.upper()}
        elif operation == "lowercase":
            return {"result": text.lower()}
        elif operation == "reverse":
            return {"result": text[::-1]}
        elif operation == "trim":
            return {"result": text.strip()}
        elif operation == "lines":
            return {"lines": text.split("\n"), "count": len(text.split("\n"))}
        else:
            return {"error": f"Unsupported operation: {operation}"}


class SummarizeWorker:
    """Text summarization."""
    worker_id = "summarize"
    version = "0.19.0"

    def execute(self, text: str, ratio: float = 0.2, max_sentences: Optional[int] = None) -> Dict[str, Any]:
        try:
            from sumy.parsers.plaintext import PlaintextParser
            from sumy.nlp.tokenizers import Tokenizer
            from sumy.summarizers.lsa import LsaSummarizer

            parser = PlaintextParser.from_string(text, Tokenizer("english"))
            summarizer = LsaSummarizer()
            sentences = summarizer(parser.document, int(len(text.split(".")) * ratio))

            if max_sentences:
                sentences = sentences[:max_sentences]

            summary = " ".join(str(s) for s in sentences)
            return {"summary": summary, "original_length": len(text), "summary_length": len(summary)}
        except ImportError:
            # Fallback: simple extractive summarization
            sentences = [s.strip() for s in text.split(".") if s.strip()]
            if max_sentences:
                sentences = sentences[:max_sentences]
            return {"summary": ". ".join(sentences) + ".", "method": "fallback", "original_length": len(text)}
        except Exception as e:
            return {"error": str(e)}


class TranslateWorker:
    """Text translation."""
    worker_id = "translate"
    version = "0.19.0"

    def execute(self, text: str, source_lang: str = "en", target_lang: str = "es") -> Dict[str, Any]:
        try:
            from deep_translator import GoogleTranslator
            translated = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
            return {"translated": translated, "source": source_lang, "target": target_lang}
        except ImportError:
            return {"error": "deep_translator required: pip install deep-translator"}
        except Exception as e:
            return {"error": str(e)}


class SentimentWorker:
    """Sentiment analysis."""
    worker_id = "sentiment"
    version = "0.19.0"

    def execute(self, text: str) -> Dict[str, Any]:
        try:
            from textblob import TextBlob
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity

            if polarity > 0.1:
                sentiment = "positive"
            elif polarity < -0.1:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            return {
                "text": text[:200],
                "sentiment": sentiment,
                "polarity": polarity,
                "subjectivity": subjectivity,
            }
        except ImportError:
            return {"error": "textblob required: pip install textblob"}
        except Exception as e:
            return {"error": str(e)}


class KeywordExtractWorker:
    """Extract keywords from text."""
    worker_id = "keyword_extract"
    version = "0.19.0"

    def execute(self, text: str, top_n: int = 10) -> Dict[str, Any]:
        try:
            from keybert import KeyBERT
            kw_model = KeyBERT()
            keywords = kw_model.extract_keywords(text, top_n=top_n)
            return {"keywords": [k[0] for k in keywords], "scores": [k[1] for k in keywords]}
        except ImportError:
            # Fallback: simple word frequency
            import re
            from collections import Counter
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            stop_words = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "her", "was", "one", "our", "out", "has", "have", "had", "him", "his", "how", "its", "may", "new", "now", "old", "see", "way", "did", "let", "say", "she", "too", "use", "big", "end", "get", "got", "just", "made", "make", "many", "most", "much", "must", "need", "never", "only", "over", "really", "should", "take", "than", "them", "then", "there", "these", "they", "think", "this", "those", "through", "under", "want", "what", "when", "where", "which", "while", "who", "will", "with", "would", "year", "years", "about", "after", "also", "back", "been", "before", "being", "between", "both", "come", "could", "day", "even", "first", "from", "give", "good", "great", "here", "into", "keep", "know", "last", "like", "life", "little", "long", "look", "more", "other", "people", "place", "right", "same", "some", "such", "take", "tell", "time", "turn", "upon", "used", "very", "well", "work", "world"}
            words = [w for w in words if w not in stop_words]
            common = Counter(words).most_common(top_n)
            return {"keywords": [w[0] for w in common], "fallback": True}
        except Exception as e:
            return {"error": str(e)}


class EntityExtractWorker:
    """Named entity recognition."""
    worker_id = "entity_extract"
    version = "0.19.0"

    def execute(self, text: str) -> Dict[str, Any]:
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
            doc = nlp(text)
            entities = [(ent.text, ent.label_, ent.start_char, ent.end_char) for ent in doc.ents]
            return {"entities": entities, "count": len(entities)}
        except ImportError:
            return {"error": "spacy required: pip install spacy && python -m spacy download en_core_web_sm"}
        except Exception as e:
            return {"error": str(e)}


class RegexWorker:
    """Regular expression operations."""
    worker_id = "regex"
    version = "0.19.0"

    def execute(self, text: str, pattern: str, operation: str = "match", flags: int = 0) -> Dict[str, Any]:
        import re
        try:
            if operation == "match":
                match = re.match(pattern, text, flags)
                if match:
                    return {"match": match.group(), "groups": match.groups(), "span": match.span()}
                return {"match": None}
            elif operation == "search":
                match = re.search(pattern, text, flags)
                if match:
                    return {"match": match.group(), "groups": match.groups(), "span": match.span()}
                return {"match": None}
            elif operation == "findall":
                matches = re.findall(pattern, text, flags)
                return {"matches": matches, "count": len(matches)}
            elif operation == "sub":
                replacement = flags if isinstance(flags, str) else ""
                return {"result": re.sub(pattern, replacement, text)}
            elif operation == "split":
                return {"parts": re.split(pattern, text, flags)}
            else:
                return {"error": f"Unsupported operation: {operation}"}
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}


class TextDiffWorker:
    """Text diff/patch."""
    worker_id = "text_diff"
    version = "0.19.0"

    def execute(self, text1: str, text2: str, operation: str = "diff") -> Dict[str, Any]:
        import difflib
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        if operation == "diff":
            diff = list(difflib.unified_diff(lines1, lines2, lineterm=""))
            return {"diff": "".join(diff), "identical": len(diff) == 0}
        elif operation == "similarity":
            matcher = difflib.SequenceMatcher(None, text1, text2)
            return {"similarity": matcher.ratio(), "matching_chars": matcher.find_longest_match(0, len(text1), 0, len(text2)).size}
        else:
            return {"error": f"Unsupported operation: {operation}"}


class PlagiarismCheckWorker:
    """Simple plagiarism detection."""
    worker_id = "plagiarism_check"
    version = "0.19.0"

    def execute(self, text1: str, text2: str) -> Dict[str, Any]:
        import difflib
        similarity = difflib.SequenceMatcher(None, text1, text2).ratio()

        # Word-level comparison
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        common_words = words1 & words2
        word_overlap = len(common_words) / max(len(words1), len(words2)) if words1 or words2 else 0

        return {
            "char_similarity": similarity,
            "word_overlap": word_overlap,
            "likely_plagiarized": similarity > 0.7 or word_overlap > 0.8,
        }
