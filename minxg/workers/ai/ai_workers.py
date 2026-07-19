"""
MINXG AI Workers — AI/ML operations and model interactions.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional


class ChatWorker:
    """AI chat completion."""
    worker_id = "ai_chat"
    version = "0.19.0"

    def execute(self, messages: List[Dict[str, str]], model: str = "gpt-4o",
                temperature: float = 0.3, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        try:
            from openai import OpenAI
            client = OpenAI()
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            response = client.chat.completions.create(**kwargs)
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }
        except ImportError:
            return {"error": "openai package required: pip install openai"}
        except Exception as e:
            return {"error": str(e)}


class EmbeddingsWorker:
    """Generate embeddings."""
    worker_id = "embeddings"
    version = "0.19.0"

    def execute(self, text: str, model: str = "text-embedding-3-small") -> Dict[str, Any]:
        try:
            from openai import OpenAI
            client = OpenAI()
            response = client.embeddings.create(input=text, model=model)
            return {
                "embedding": response.data[0].embedding[:100],  # Limit output
                "dimensions": len(response.data[0].embedding),
                "model": response.model,
            }
        except ImportError:
            return {"error": "openai package required: pip install openai"}
        except Exception as e:
            return {"error": str(e)}


class ClassifyWorker:
    """Text classification."""
    worker_id = "classify"
    version = "0.19.0"

    def execute(self, text: str, categories: List[str]) -> Dict[str, Any]:
        # Simple keyword-based classification
        text_lower = text.lower()
        scores = {}
        for cat in categories:
            cat_lower = cat.lower()
            # Count keyword occurrences
            score = text_lower.count(cat_lower)
            # Also check related terms
            scores[cat] = score

        # Normalize
        total = sum(scores.values()) or 1
        return {
            "text": text[:200],
            "categories": {cat: score / total for cat, score in scores.items()},
            "predicted": max(scores, key=scores.get) if scores else None,
        }


class ExtractWorker:
    """Information extraction."""
    worker_id = "extract"
    version = "0.19.0"

    def execute(self, text: str, entity_types: Optional[List[str]] = None) -> Dict[str, Any]:
        import re

        if entity_types is None:
            entity_types = ["email", "phone", "url", "date", "money", "ip"]

        results = {}

        if "email" in entity_types:
            results["emails"] = re.findall(r"[\w.-]+@[\w.-]+\.\w+", text)

        if "phone" in entity_types:
            results["phones"] = re.findall(r"\+?[\d\s()-]{7,20}", text)

        if "url" in entity_types:
            results["urls"] = re.findall(r"https?://[\w./?=&#-]+", text)

        if "date" in entity_types:
            results["dates"] = re.findall(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text)

        if "money" in entity_types:
            results["money"] = re.findall(r"\$[\d,]+\.?\d*", text)

        if "ip" in entity_types:
            results["ips"] = re.findall(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", text)

        return {"text": text[:500], "entities": results}


class OCRWorker:
    """Optical character recognition."""
    worker_id = "ocr"
    version = "0.19.0"

    def execute(self, image_path: str, language: str = "eng") -> Dict[str, Any]:
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang=language)
            return {"text": text, "language": language, "source": image_path}
        except ImportError:
            return {"error": "pytesseract and PIL required: pip install pytesseract pillow"}
        except Exception as e:
            return {"error": str(e)}


class SpeechToTextWorker:
    """Speech to text transcription."""
    worker_id = "speech_to_text"
    version = "0.19.0"

    def execute(self, audio_path: str, language: str = "en") -> Dict[str, Any]:
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language=language)
            return {
                "text": result["text"],
                "language": result.get("language", language),
                "segments": result.get("segments", [])[:10],
            }
        except ImportError:
            return {"error": "openai-whisper required: pip install openai-whisper"}
        except Exception as e:
            return {"error": str(e)}


class TextToSpeechWorker:
    """Text to speech synthesis."""
    worker_id = "text_to_speech"
    version = "0.19.0"

    def execute(self, text: str, output_path: str, voice: str = "default") -> Dict[str, Any]:
        try:
            # Try using system TTS
            import subprocess
            import platform

            if platform.system() == "Darwin":
                subprocess.run(["say", "-o", output_path, text])
            elif platform.system() == "Linux":
                subprocess.run(["espeak", "-w", output_path, text])
            else:
                return {"error": "TTS not supported on this platform"}

            return {"output": output_path, "voice": voice, "text_length": len(text)}
        except Exception as e:
            return {"error": str(e)}


class SummarizeLongWorker:
    """Summarize long documents."""
    worker_id = "summarize_long"
    version = "0.19.0"

    def execute(self, text: str, max_length: int = 500) -> Dict[str, Any]:
        # Chunk and summarize
        sentences = text.split(". ")
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) > 1000:
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                current_chunk += ". " + sentence
        if current_chunk:
            chunks.append(current_chunk)

        # Extract key sentences from each chunk
        key_sentences = []
        for chunk in chunks:
            chunk_sentences = [s.strip() for s in chunk.split(".") if len(s.strip()) > 20]
            if chunk_sentences:
                key_sentences.append(chunk_sentences[0])  # Take first sentence as key

        summary = ". ".join(key_sentences[:20]) + "."

        return {
            "summary": summary,
            "original_length": len(text),
            "summary_length": len(summary),
            "compression_ratio": len(summary) / max(1, len(text)),
            "chunks_processed": len(chunks),
        }


class QuestionAnswerWorker:
    """Question answering."""
    worker_id = "question_answer"
    version = "0.19.0"

    def execute(self, question: str, context: Optional[str] = None) -> Dict[str, Any]:
        # Simple keyword matching for QA
        question_lower = question.lower()

        # Detect question type
        if question_lower.startswith("what"):
            qa_type = "definition"
        elif question_lower.startswith("who"):
            qa_type = "person"
        elif question_lower.startswith("when"):
            qa_type = "time"
        elif question_lower.startswith("where"):
            qa_type = "location"
        elif question_lower.startswith("why"):
            qa_type = "reason"
        elif question_lower.startswith("how"):
            if "many" in question_lower or "much" in question_lower:
                qa_type = "quantity"
            else:
                qa_type = "method"
        else:
            qa_type = "general"

        return {
            "question": question,
            "question_type": qa_type,
            "context_length": len(context) if context else 0,
            "note": "Use context parameter for better answers",
        }
