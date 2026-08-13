"""
Quiz Generator Service

Generates multiple-choice quiz questions (single- and multi-select)
from documents using the configured LLM.
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.llm_client import call_llm

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_QUESTION_TYPES = {"single", "multiple"}
MAX_GENERATION_ATTEMPTS = 3

LETTER_TO_INDEX = {"a": 0, "b": 1, "c": 2, "d": 3}

JSON_ARRAY_GRAMMAR = r"""root ::= ws "[" ws item ws "," ws item ws "," ws item ws "," ws item ws "," ws item (ws "," ws item)* ws "]" ws
item ::= "{" ws "type" ws ":" ws ("single" | "multiple") ws "," ws "text" ws ":" ws string ws "," ws "options" ws ":" ws "[" ws string ws "," ws string ws "," ws string ws "," ws string ws "]" ws "," ws "answer" ws ":" ws "[" ws num (ws "," ws num)* ws "]" ws "," ws "explanation" ws ":" ws string ws "}" ws
num ::= "0" | "1" | "2" | "3"
string ::= "\"" chars "\""
chars ::= char chars | ""
char ::= [^"\\] | "\\" (["\\/bfnrt] | "u" [0-9A-Fa-f]{4})
ws ::= [ \t\n]*
"""

DIFFICULTY_PROMPTS = {
    "easy": "basic recall of key facts and definitions from the content",
    "medium": "understanding and application of core concepts from the content",
    "hard": "analysis, synthesis, and distinguishing subtle differences between concepts",
}


class QuizGenerationError(Exception):
    """Exception raised for quiz generation errors."""


def _fix_letter_answers(text: str) -> str:
    """Convert letter-style answer values (e.g. [A, C] or "B") to numeric indices."""
    key_pattern = r'["\'`]?answer["\'`]?\s*:\s*'

    def replace_list(match: re.Match) -> str:
        tokens = [t.strip() for t in match.group(2).split(",") if t.strip()]
        if tokens and all(t.lower() in LETTER_TO_INDEX for t in tokens):
            indexes = [str(LETTER_TO_INDEX[t.lower()]) for t in tokens]
            return f'{match.group(1)}[{", ".join(indexes)}]'
        return match.group(0)

    def replace_quoted(match: re.Match) -> str:
        letter = match.group(2).lower()
        if letter in LETTER_TO_INDEX:
            return f"{match.group(1)}[{LETTER_TO_INDEX[letter]}]"
        return match.group(0)

    text = re.sub(rf"({key_pattern})\[([A-Za-z\s,]+)\]", replace_list, text)
    text = re.sub(rf"({key_pattern})(['\"])([A-Da-d])\2", replace_quoted, text)
    return text


def _coerce_answer(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean answer is not valid")
    if isinstance(value, int):
        return value
    token = str(value).strip().lower()
    if token in LETTER_TO_INDEX:
        return LETTER_TO_INDEX[token]
    return int(token)


def _quote_keys(text: str) -> str:
    """Quote unquoted or single-quoted JSON keys emitted by small LLMs."""
    text = re.sub(
        r"([\[,{]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)",
        r'\1"\2"\3',
        text,
    )
    text = re.sub(
        r"([\[,{]\s*)'([A-Za-z_][A-Za-z0-9_]*)'(\s*:)",
        r'\1"\2"\3',
        text,
    )
    text = re.sub(
        r"(:\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*[,}\]])",
        r'\1"\2"\3',
        text,
    )
    return text


def _fix_inner_quotes(text: str) -> str:
    """Replace embedded double quotes (word surrounded by spaces) with single quotes."""
    return re.sub(
        r'(?<=\s)"([A-Za-z][^"\n]*?)"(?=\s[A-Za-z])',
        lambda match: "'" + match.group(1) + "'",
        text,
    )


class QuizGenerator:
    """Quiz generation service using the configured LLM."""

    def __init__(self, llm_provider: Optional[str] = None, model: Optional[str] = None):
        from app.services.runtime_llm import load_runtime_llm_settings

        rt = load_runtime_llm_settings()
        self.llm_provider = llm_provider or rt["provider"] or settings.LLM_PROVIDER
        self.model = model or rt["model"] or settings.LOCAL_LLM_MODEL
        self.base_url = rt["base_url"] or settings.LOCAL_LLM_BASE_URL
        self.timeout = settings.LOCAL_LLM_TIMEOUT_SECONDS

    def _build_prompt(
        self, documents: List[Dict[str, Any]], config: Dict[str, Any]
    ) -> str:
        num_questions = int(config["num_questions"])
        difficulty = config["difficulty"]
        question_types = config["question_types"]
        single_count = int(question_types.get("single", 0))
        multiple_count = int(question_types.get("multiple", 0))

        doc_list = "\n\n".join(
            f"### Document: {doc['name']}\n{doc['text'][:5000]}" for doc in documents
        )

        return f"""Generate {num_questions} multiple-choice quiz questions based ONLY on the following document(s).

{doc_list}

Requirements:
- {single_count} single-choice question(s): exactly ONE correct option.
- {multiple_count} multiple-choice question(s): TWO OR MORE correct options.
- Difficulty: {DIFFICULTY_PROMPTS[difficulty]}.
- Each question has exactly 4 options with plausible distractors grounded in the content.
- Provide a concise explanation of the correct answer for every question.

Respond with ONLY a JSON array (no markdown fences, no extra text) in this exact format:
[
  {{"type": "single", "text": "Question text?", "options": ["A", "B", "C", "D"], "answer": [2], "explanation": "Why option index 2 is correct."}},
  {{"type": "multiple", "text": "Question text?", "options": ["A", "B", "C", "D"], "answer": [0, 3], "explanation": "Why options 0 and 3 are correct."}}
]"""

    def _build_messages(self, prompt: str) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are an exam question generator for lecture notes. "
                    "Generate accurate questions grounded in the provided content. "
                    "Output ONLY valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ]

    def _call_local_llm(self, prompt: str) -> str:
        try:
            messages = self._build_messages(prompt)
            result = call_llm(
                provider="local_llm",
                model=self.model,
                call_type="quiz",
                messages=messages,
                base_url=self.base_url,
                timeout=self.timeout,
                num_predict=4096,
                grammar=JSON_ARRAY_GRAMMAR,
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except Exception as exc:
            raise QuizGenerationError(f"Failed to call local LLM: {str(exc)}") from exc

    def _call_gemini(self, prompt: str) -> str:
        try:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                raise QuizGenerationError("Gemini API key not configured")
            messages = self._build_messages(prompt)
            result = call_llm(
                provider="gemini",
                model=settings.GEMINI_MODEL,
                call_type="quiz",
                messages=messages,
                api_key=api_key,
                base_url=settings.GEMINI_BASE_URL,
                temperature=0.3,
                max_tokens=4096,
                response_format="json",
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except QuizGenerationError:
            raise
        except Exception as exc:
            raise QuizGenerationError(f"Failed to call Gemini: {str(exc)}") from exc

    def _call_openrouter(self, prompt: str) -> str:
        try:
            api_key = settings.OPENROUTER_API_KEY
            if not api_key:
                raise QuizGenerationError("OpenRouter API key not configured")
            messages = self._build_messages(prompt)
            result = call_llm(
                provider="openrouter",
                model=settings.OPENROUTER_MODEL,
                call_type="quiz",
                messages=messages,
                api_key=api_key,
                base_url=settings.OPENROUTER_BASE_URL,
                temperature=0.3,
                max_tokens=4096,
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except QuizGenerationError:
            raise
        except Exception as exc:
            raise QuizGenerationError(f"Failed to call OpenRouter: {str(exc)}") from exc

    def _call_llm(self, prompt: str) -> str:
        if self.llm_provider == "local_llm":
            return self._call_local_llm(prompt)
        if self.llm_provider == "gemini":
            return self._call_gemini(prompt)
        if self.llm_provider == "openrouter":
            return self._call_openrouter(prompt)
        raise QuizGenerationError(f"Unknown LLM provider: {self.llm_provider}")

    def _extract_json(self, raw: str) -> Any:
        text = str(raw).strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        text = _fix_inner_quotes(text)
        text = _fix_letter_answers(text)
        text = _quote_keys(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for start in [i for i, ch in enumerate(text) if ch in "[{"]:
            try:
                value, _ = decoder.raw_decode(text, start)
            except json.JSONDecodeError:
                continue
            if isinstance(value, list) and (
                not value or all(isinstance(item, dict) for item in value)
            ):
                return value

        raise QuizGenerationError("LLM output contains no valid JSON array")

    def _normalize_question(self, raw: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(raw, dict):
            return None

        q_type = str(raw.get("type", "")).strip().lower()
        if q_type not in VALID_QUESTION_TYPES:
            return None

        text = str(raw.get("text", "")).strip()
        if not text:
            return None

        options = raw.get("options")
        if not isinstance(options, list) or len(options) < 2:
            return None
        options = [str(option).strip() for option in options]
        if any(not option for option in options):
            return None

        answer = raw.get("answer", [])
        if isinstance(answer, int):
            answer = [answer]
        if isinstance(answer, str):
            answer = [answer]
        if not isinstance(answer, list) or not answer:
            return None
        try:
            answer_indexes = [_coerce_answer(a) for a in answer]
        except (TypeError, ValueError):
            return None
        if any(idx < 0 or idx >= len(options) for idx in answer_indexes):
            return None
        answer_indexes = sorted(set(answer_indexes))
        if q_type == "single":
            answer_indexes = answer_indexes[:1]

        explanation = str(raw.get("explanation", "")).strip()
        if not explanation:
            return None

        return {
            "type": q_type,
            "text": text,
            "options": options,
            "answer": answer_indexes,
            "explanation": explanation,
        }

    def generate_quiz(
        self, documents: List[Dict[str, Any]], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a quiz from the given documents.

        Args:
            documents: List of document dicts with name and text
            config: Quiz config with num_questions, difficulty, question_types

        Returns:
            Dict with questions (including answers) and config

        Raises:
            QuizGenerationError: If generation fails after retries
        """
        if not documents:
            raise QuizGenerationError("No documents provided")

        expected_count = int(config["num_questions"])
        last_error = None
        for _ in range(MAX_GENERATION_ATTEMPTS):
            try:
                prompt = self._build_prompt(documents, config)
                raw = self._call_llm(prompt)
                data = self._extract_json(raw)
                if isinstance(data, dict):
                    if "questions" not in data:
                        raise QuizGenerationError(
                            "LLM JSON object missing 'questions' key"
                        )
                    data = data["questions"]
                if not isinstance(data, list):
                    raise QuizGenerationError(
                        "LLM output must be a JSON array of questions"
                    )

                questions = []
                for item in data:
                    normalized = self._normalize_question(item)
                    if normalized is not None:
                        questions.append(normalized)

                if len(questions) < expected_count:
                    raise QuizGenerationError(
                        f"Expected {expected_count} questions, got {len(questions)}"
                    )
                if len(questions) > expected_count:
                    questions = questions[:expected_count]
                return {"questions": questions, "config": config}
            except QuizGenerationError as exc:
                last_error = exc

        raise QuizGenerationError(
            f"Quiz generation failed after {MAX_GENERATION_ATTEMPTS} attempts: {last_error}"
        )
