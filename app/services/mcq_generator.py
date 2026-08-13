"""
MCQ Generation Service for creating multiple-choice questions from lecture
documents using an LLM-first approach.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.runtime_llm import (
    load_runtime_llm_settings,
    resolve_gemini_api_model,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
MCQ_TIMEOUT_SECONDS = 60
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
MAX_QUESTIONS = 20

DIFFICULTY_HINTS = {
    "mixed": (
        "Vary the difficulty: roughly one third easy (recall of facts), "
        "one third medium (understanding), one third hard "
        "(analysis/application)."
    ),
    "easy": "All questions should be easy: simple recall of key facts "
    "and definitions.",
    "medium": "All questions should be medium: understanding and "
    "explanation of concepts.",
    "hard": "All questions should be hard: analysis, comparison, and " "application.",
}


class MCQGenerationError(Exception):
    """Custom exception for MCQ generation errors."""


class MCQGeneratorService:
    """
    Service for generating multiple-choice questions from documents.

    Uses an LLM-first approach: ask the LLM to produce a JSON quiz, then
    parse, validate, and (on malformed output) retry up to MAX_RETRIES
    times. There is no template fallback — failures raise
    MCQGenerationError.
    """

    def __init__(self, llm_provider: Optional[str] = None):
        runtime = load_runtime_llm_settings()
        self.llm_provider = llm_provider or runtime["provider"] or settings.LLM_PROVIDER
        self._runtime_model = runtime["model"]
        self._runtime_api_key = runtime["api_key"]
        self._runtime_base_url = runtime["base_url"]

    def generate_mcqs(
        self,
        documents: List[Dict[str, Any]],
        num_questions: int = 5,
        difficulty: str = "mixed",
        timeout_seconds: int = MCQ_TIMEOUT_SECONDS,
    ) -> List[Dict[str, Any]]:
        """Generate validated MCQs from documents (LLM-first, retry)."""
        if not documents:
            raise MCQGenerationError("No documents provided for MCQ generation")

        num_questions = max(1, min(int(num_questions), MAX_QUESTIONS))
        if difficulty not in {"mixed", "easy", "medium", "hard"}:
            difficulty = "mixed"

        prompt = self._build_prompt(documents, num_questions, difficulty)
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._call_llm_with_timeout(prompt, timeout_seconds)
                data = self._parse_json_response(response)
                questions = self._validate_questions(data, num_questions)
                logger.info(
                    "Generated %d MCQs (attempt %d)",
                    len(questions),
                    attempt + 1,
                )
                return questions
            except TimeoutError as exc:
                raise MCQGenerationError(f"LLM call timed out: {exc}")
            except MCQGenerationError as exc:
                last_error = exc
                logger.warning("MCQ generation attempt %d failed: %s", attempt + 1, exc)

        raise MCQGenerationError(
            f"MCQ generation failed after {MAX_RETRIES + 1} attempts: " f"{last_error}"
        )

    def _call_llm_with_timeout(self, prompt: str, timeout_seconds: int) -> str:
        """Call the LLM in a thread so a timeout can be enforced on Windows."""
        import threading

        result: List[Optional[str]] = [None]
        exception: List[Optional[Exception]] = [None]

        def _run() -> None:
            try:
                result[0] = self._call_llm(prompt)
            except Exception as exc:  # noqa: BLE001
                exception[0] = exc

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            raise TimeoutError(f"LLM call timed out after {timeout_seconds}s")
        if exception[0]:
            raise exception[0]
        return result[0] or ""

    def _build_prompt(
        self,
        documents: List[Dict[str, Any]],
        num_questions: int,
        difficulty: str,
    ) -> str:
        """Build the MCQ generation prompt."""
        sections = []
        for doc in documents:
            name = doc.get("name") or doc.get("filename", "Unknown")
            content = str(doc.get("content", "") or "")
            sections.append(f"=== {name} ===\n{content[:6000]}")

        combined = "\n\n".join(sections)
        difficulty_hint = DIFFICULTY_HINTS.get(difficulty, DIFFICULTY_HINTS["mixed"])

        return f"""You are a teaching assistant creating a multiple-choice quiz from lecture notes.

Based ONLY on the following lecture content, generate EXACTLY {num_questions} multiple-choice questions.

{difficulty_hint}

Requirements:
1. Each question has 4 options labeled A, B, C, D
2. Exactly one option is correct
3. Distractors must be plausible and reflect common misconceptions
4. Include a concise explanation of why the correct answer is right
5. Question stems must be answerable from the provided content only
6. All text must be in English
7. Set "source_doc" to the document the question is based on

Lecture Content:
{combined}

Respond with ONLY a JSON object, no markdown fences or commentary, in this exact shape:
{{"questions": [{{"question": "...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct_answer": "A", "explanation": "...", "difficulty": "easy", "source_doc": "..."}}]}}"""

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Extract and parse the JSON object from the LLM response."""
        text = (response or "").strip()
        if not text:
            raise MCQGenerationError("Empty LLM response")

        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise MCQGenerationError("LLM response does not contain a JSON object")

        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise MCQGenerationError(f"Invalid JSON from LLM: {exc}")

        if not isinstance(data, dict):
            raise MCQGenerationError("LLM JSON is not an object")
        return data

    def _validate_questions(
        self, data: Dict[str, Any], num_questions: int
    ) -> List[Dict[str, Any]]:
        """Validate the parsed questions and normalize their shape."""
        raw = data.get("questions")
        if not isinstance(raw, list) or not raw:
            raise MCQGenerationError("LLM response missing 'questions' list")
        if len(raw) < num_questions:
            raise MCQGenerationError(
                f"Expected {num_questions} questions, got {len(raw)}"
            )

        questions: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw[:num_questions]):
            if not isinstance(item, dict):
                raise MCQGenerationError(f"Question {idx + 1} is not an object")

            stem = str(item.get("question", "") or "").strip()
            if not stem:
                raise MCQGenerationError(f"Question {idx + 1} has empty stem")

            options = item.get("options")
            if not isinstance(options, dict) or set(options.keys()) != {
                "A",
                "B",
                "C",
                "D",
            }:
                raise MCQGenerationError(
                    f"Question {idx + 1} must have exactly options A-D"
                )

            cleaned_options: Dict[str, str] = {}
            for label in ("A", "B", "C", "D"):
                option_text = str(options[label] or "").strip()
                if not option_text:
                    raise MCQGenerationError(
                        f"Question {idx + 1} option {label} is empty"
                    )
                cleaned_options[label] = option_text

            correct = str(item.get("correct_answer", "") or "").strip().upper()
            if correct not in {"A", "B", "C", "D"}:
                raise MCQGenerationError(
                    f"Question {idx + 1} has invalid correct_answer: " f"{correct!r}"
                )

            explanation = str(item.get("explanation", "") or "").strip()
            if not explanation:
                raise MCQGenerationError(f"Question {idx + 1} is missing explanation")

            difficulty = (
                str(item.get("difficulty", "medium") or "medium").strip().lower()
            )
            if difficulty not in VALID_DIFFICULTIES:
                difficulty = "medium"

            source_doc = str(item.get("source_doc", "") or "").strip()

            questions.append(
                {
                    "question": stem,
                    "options": cleaned_options,
                    "correct_answer": correct,
                    "explanation": explanation,
                    "difficulty": difficulty,
                    "source_doc": source_doc,
                }
            )

        return questions

    def _call_llm(self, prompt: str) -> str:
        """Dispatch to the configured LLM provider."""
        if self.llm_provider == "local_llm":
            return self._call_local_llm(prompt)
        elif self.llm_provider == "gemini":
            return self._call_gemini(prompt)
        elif self.llm_provider == "openrouter":
            return self._call_openrouter(prompt)
        raise MCQGenerationError(f"Unknown LLM provider: {self.llm_provider}")

    def _call_local_llm(self, prompt: str) -> str:
        """Call local LLM via llama.cpp."""
        try:
            from app.services.llm_client import call_llm

            return call_llm(
                provider="local_llm",
                model=self._runtime_model or settings.LOCAL_LLM_MODEL,
                call_type="mcq",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                base_url=self._runtime_base_url or settings.LOCAL_LLM_BASE_URL,
                timeout=settings.LOCAL_LLM_TIMEOUT_SECONDS,
                temperature=0.5,
                num_predict=2048,
            )
        except Exception as exc:  # noqa: BLE001
            raise MCQGenerationError(f"Local LLM call failed: {exc}")

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API."""
        try:
            from app.services.llm_client import call_llm

            api_key = self._runtime_api_key or settings.GEMINI_API_KEY
            if not api_key:
                raise MCQGenerationError("GEMINI_API_KEY is not configured")

            return call_llm(
                provider="gemini",
                model=resolve_gemini_api_model(
                    self._runtime_model, settings.GEMINI_MODEL
                ),
                call_type="mcq",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                api_key=api_key,
                base_url=self._runtime_base_url or settings.GEMINI_BASE_URL,
                temperature=0.5,
                max_tokens=2048,
                response_format="json",
            )
        except Exception as exc:  # noqa: BLE001
            raise MCQGenerationError(f"Gemini call failed: {exc}")

    def _call_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API."""
        try:
            from app.services.llm_client import call_llm

            api_key = self._runtime_api_key or settings.OPENROUTER_API_KEY
            if not api_key:
                raise MCQGenerationError("OPENROUTER_API_KEY is not configured")

            return call_llm(
                provider="openrouter",
                model=self._runtime_model or settings.OPENROUTER_MODEL,
                call_type="mcq",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                api_key=api_key,
                base_url=self._runtime_base_url or settings.OPENROUTER_BASE_URL,
                temperature=0.5,
                max_tokens=2048,
            )
        except Exception as exc:  # noqa: BLE001
            raise MCQGenerationError(f"OpenRouter call failed: {exc}")


__all__ = [
    "DIFFICULTY_HINTS",
    "MAX_QUESTIONS",
    "MAX_RETRIES",
    "MCQGenerationError",
    "MCQGeneratorService",
    "MCQ_TIMEOUT_SECONDS",
    "VALID_DIFFICULTIES",
]
