"""
MINXG Guardrails — Input validation, output filtering, and safety checks.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import re


class GuardResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    MODIFY = "modify"


@dataclass
class GuardResponse:
    """Result of a guardrail check."""
    result: GuardResult
    message: str = ""
    modified_content: Optional[str] = None
    confidence: float = 1.0


class InputGuardrail:
    """Validate and filter user inputs."""

    def __init__(self):
        self.checks: List[Callable[[str], GuardResponse]] = []
        self._setup_default_checks()

    def _setup_default_checks(self):
        """Setup default input checks."""
        self.add_check(self._check_max_length)
        self.add_check(self._check_injection)
        self.add_check(self._check_pii)
        self.add_check(self._check_toxicity)

    def add_check(self, check: Callable[[str], GuardResponse]) -> None:
        """Add a custom check."""
        self.checks.append(check)

    def validate(self, text: str) -> GuardResponse:
        """Run all checks on input text."""
        for check in self.checks:
            result = check(text)
            if result.result == GuardResult.FAIL:
                return result
            if result.result == GuardResult.MODIFY:
                text = result.modified_content or text
        return GuardResponse(GuardResult.PASS, "Input passed all checks")

    @staticmethod
    def _check_max_length(text: str) -> GuardResponse:
        """Check input length."""
        if len(text) > 100000:
            return GuardResponse(
                GuardResult.FAIL,
                f"Input too long: {len(text)} chars (max: 100000)",
            )
        return GuardResponse(GuardResult.PASS)

    @staticmethod
    def _check_injection(text: str) -> GuardResponse:
        """Check for prompt injection attempts."""
        injection_patterns = [
            r"ignore\s+previous\s+instructions",
            r"disregard\s+(all|the\s+above|previous)",
            r"you\s+are\s+now\s+",
            r"new\s+instructions?\s*:",
            r"system\s*:\s*override",
            r"<\|im_start\|>",
            r"<\|im_end\|>",
            r"developer\s*mode",
            r"DAN\s+mode",
        ]

        text_lower = text.lower()
        for pattern in injection_patterns:
            if re.search(pattern, text_lower):
                return GuardResponse(
                    GuardResult.FAIL,
                    "Potential prompt injection detected",
                    confidence=0.9,
                )
        return GuardResponse(GuardResult.PASS)

    @staticmethod
    def _check_pii(text: str) -> GuardResponse:
        """Check for personally identifiable information."""
        pii_patterns = {
            "email": r"[\w.-]+@[\w.-]+\.\w+",
            "phone": r"\+?[\d\s()-]{7,20}",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
            "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        }

        found = []
        for pii_type, pattern in pii_patterns.items():
            if re.search(pattern, text):
                found.append(pii_type)

        if found:
            return GuardResponse(
                GuardResult.MODIFY,
                f"PII detected: {', '.join(found)}. Consider redacting.",
                modified_content=Guardrails._redact_pii(text),
            )
        return GuardResponse(GuardResult.PASS)

    @staticmethod
    def _check_toxicity(text: str) -> GuardResponse:
        """Simple toxicity check."""
        toxic_words = [
            "hate", "kill", "die", "stupid", "idiot", "retard",
            "nigger", "faggot", "cunt", "fuck", "shit", "asshole",
        ]
        text_lower = text.lower()
        toxic_count = sum(1 for word in toxic_words if word in text_lower)

        if toxic_count > 3:
            return GuardResponse(
                GuardResult.FAIL,
                "Content appears to be toxic or abusive",
                confidence=toxic_count / len(toxic_words),
            )
        return GuardResponse(GuardResult.PASS)


class OutputGuardrail:
    """Validate and filter AI outputs."""

    def __init__(self):
        self.checks: List[Callable[[str], GuardResponse]] = []
        self._setup_default_checks()

    def _setup_default_checks(self):
        """Setup default output checks."""
        self.add_check(self._check_max_length)
        self.add_check(self._check_hallucination)
        self.add_check(self._check_repetition)
        self.add_check(self._check_code_injection)

    def add_check(self, check: Callable[[str], GuardResponse]) -> None:
        """Add a custom check."""
        self.checks.append(check)

    def validate(self, text: str) -> GuardResponse:
        """Run all checks on output text."""
        for check in self.checks:
            result = check(text)
            if result.result == GuardResult.FAIL:
                return result
        return GuardResponse(GuardResult.PASS, "Output passed all checks")

    @staticmethod
    def _check_max_length(text: str) -> GuardResponse:
        """Check output length."""
        if len(text) > 50000:
            return GuardResponse(
                GuardResult.FAIL,
                f"Output too long: {len(text)} chars (max: 50000)",
            )
        return GuardResponse(GuardResult.PASS)

    @staticmethod
    def _check_hallucination(text: str) -> GuardResponse:
        """Check for hallucination indicators."""
        hallucination_phrases = [
            "i'm confident that",
            "i know for a fact",
            "definitely true that",
            "100% certain",
            "absolutely verified",
        ]
        text_lower = text.lower()
        for phrase in hallucination_phrases:
            if phrase in text_lower:
                return GuardResponse(
                    GuardResult.FAIL,
                    "Potential hallucination detected - overly confident claims",
                    confidence=0.7,
                )
        return GuardResponse(GuardResult.PASS)

    @staticmethod
    def _check_repetition(text: str) -> GuardResponse:
        """Check for excessive repetition."""
        sentences = re.split(r'[.!?]+', text)
        if len(sentences) < 3:
            return GuardResponse(GuardResult.PASS)

        # Check for repeated sentences
        unique = set(s.strip() for s in sentences if s.strip())
        if len(unique) < len(sentences) * 0.3:
            return GuardResponse(
                GuardResult.FAIL,
                "Excessive repetition detected in output",
                confidence=0.8,
            )
        return GuardResponse(GuardResult.PASS)

    @staticmethod
    def _check_code_injection(text: str) -> GuardResponse:
        """Check for code injection attempts."""
        dangerous_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript\s*:",
            r"on(load|error|click)\s*=",
            r"eval\s*\(",
            r"exec\s*\(",
            r"os\.system\s*\(",
            r"subprocess\s*\.",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                return GuardResponse(
                    GuardResult.FAIL,
                    "Potential code injection detected",
                    confidence=0.9,
                )
        return GuardResponse(GuardResult.PASS)


class Guardrails:
    """Combined input/output guardrail system."""

    def __init__(self):
        self.input_guard = InputGuardrail()
        self.output_guard = OutputGuardrail()
        self.enabled = True

    def validate_input(self, text: str) -> GuardResponse:
        """Validate user input."""
        if not self.enabled:
            return GuardResponse(GuardResult.PASS)
        return self.input_guard.validate(text)

    def validate_output(self, text: str) -> GuardResponse:
        """Validate AI output."""
        if not self.enabled:
            return GuardResponse(GuardResult.PASS)
        return self.output_guard.validate(text)

    def process_conversation(
        self,
        user_input: str,
        ai_output: str,
    ) -> Dict[str, Any]:
        """Process a complete conversation turn."""
        input_result = self.validate_input(user_input)
        if input_result.result == GuardResult.FAIL:
            return {
                "blocked": True,
                "stage": "input",
                "reason": input_result.message,
                "safe_input": input_result.modified_content,
            }

        output_result = self.validate_output(ai_output)
        if output_result.result == GuardResult.FAIL:
            return {
                "blocked": True,
                "stage": "output",
                "reason": output_result.message,
            }

        return {
            "blocked": False,
            "input_check": input_result.result.value,
            "output_check": output_result.result.value,
        }

    @staticmethod
    def _redact_pii(text: str) -> str:
        """Redact PII from text."""
        text = re.sub(r"[\w.-]+@[\w.-]+\.\w+", "[EMAIL]", text)
        text = re.sub(r"\+?[\d\s()-]{7,20}", "[PHONE]", text)
        text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", text)
        text = re.sub(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CARD]", text)
        return text


# Global guardrails instance
_default_guardrails: Optional[Guardrails] = None


def get_guardrails() -> Guardrails:
    """Get the default guardrails instance."""
    global _default_guardrails
    if _default_guardrails is None:
        _default_guardrails = Guardrails()
    return _default_guardrails
