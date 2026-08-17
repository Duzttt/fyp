"""
Flashcard Generator Service

Generates study flashcards (front/back pairs) from documents using the
configured LLM. Each card has a prompt on the front and the recall answer,
an optional hint, and optional tags on the back.
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.llm_client import call_llm

MAX_GENERATION_ATTEMPTS = 3

JSON_ARRAY_GRAMMAR = r"""root ::= ws "[" ws item (ws "," ws item)* ws "]" ws
item ::= "{" ws "front" ws ":" ws string ws "," ws "back" ws ":" ws string ws "," ws "hint" ws ":" ws string ws "," ws "tags" ws ":" ws "[" ws string (ws "," ws string)* ws "]" ws "}" ws
string ::= "\"" chars "\""
chars ::= char chars | ""
char ::= [^"\\] | "\\" (["\\/bfnrt] | "u" [0-9A-Fa-f]{4})
ws ::= [ \t\n]*
"""


class FlashcardGenerationError(Exception):
    """Exception raised for flashcard generation errors."""


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
        r"(\s*:)([A-Za-z_][A-Za-z0-9_]*)(\s*[,}\]])",
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


class FlashcardGenerator:
    """Flashcard generation service using the configured LLM."""

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
        num_cards = int(config["num_cards"])
        topic = str(config.get("topic") or "").strip()

        doc_list = "\n\n".join(
            f"### Document: {doc['name']}\n{doc['text'][:5000]}" for doc in documents
        )

        topic_line = (
            f'\n- Focus the cards on this topic or area: "{topic}".' if topic else ""
        )

        return f"""Generate {num_cards} study flashcards based ONLY on the following document(s).

{doc_list}

Requirements:
- {num_cards} cards total, each a single concise question-and-answer pair.
- "front": a clear question, term, or prompt that tests recall.
- "back": a concise, correct answer grounded strictly in the content.
- "hint": an optional short clue to jog memory without giving the answer away.
- "tags": an optional list of 1-3 short lowercase topic labels.
{topic_line}
Respond with ONLY a JSON array (no markdown fences, no extra text) in this exact format:
[
  {{"front": "Question or term?", "back": "Answer in 1-2 sentences.", "hint": "Optional clue.", "tags": ["concept", "definition"]}},
  {{"front": "Question or term?", "back": "Answer in 1-2 sentences.", "hint": "", "tags": []}}
]"""

    def _build_messages(self, prompt: str) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a study-aid generator for lecture notes. "
                    "Generate accurate flashcards grounded in the provided content. "
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
                call_type="flashcards",
                messages=messages,
                base_url=self.base_url,
                timeout=self.timeout,
                num_predict=4096,
                grammar=JSON_ARRAY_GRAMMAR,
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except Exception as exc:
            raise FlashcardGenerationError(
                f"Failed to call local LLM: {str(exc)}"
            ) from exc

    def _call_gemini(self, prompt: str) -> str:
        try:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                raise FlashcardGenerationError("Gemini API key not configured")
            messages = self._build_messages(prompt)
            result = call_llm(
                provider="gemini",
                model=settings.GEMINI_MODEL,
                call_type="flashcards",
                messages=messages,
                api_key=api_key,
                base_url=settings.GEMINI_BASE_URL,
                temperature=0.3,
                max_tokens=4096,
                response_format="json",
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except FlashcardGenerationError:
            raise
        except Exception as exc:
            raise FlashcardGenerationError(
                f"Failed to call Gemini: {str(exc)}"
            ) from exc

    def _call_openrouter(self, prompt: str) -> str:
        try:
            api_key = settings.OPENROUTER_API_KEY
            if not api_key:
                raise FlashcardGenerationError("OpenRouter API key not configured")
            messages = self._build_messages(prompt)
            result = call_llm(
                provider="openrouter",
                model=settings.OPENROUTER_MODEL,
                call_type="flashcards",
                messages=messages,
                api_key=api_key,
                base_url=settings.OPENROUTER_BASE_URL,
                temperature=0.3,
                max_tokens=4096,
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except FlashcardGenerationError:
            raise
        except Exception as exc:
            raise FlashcardGenerationError(
                f"Failed to call OpenRouter: {str(exc)}"
            ) from exc

    def _call_llm(self, prompt: str) -> str:
        if self.llm_provider == "local_llm":
            return self._call_local_llm(prompt)
        if self.llm_provider == "gemini":
            return self._call_gemini(prompt)
        if self.llm_provider == "openrouter":
            return self._call_openrouter(prompt)
        raise FlashcardGenerationError(f"Unknown LLM provider: {self.llm_provider}")

    def _extract_json(self, raw: str) -> Any:
        text = str(raw).strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        text = _fix_inner_quotes(text)
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

        raise FlashcardGenerationError("LLM output contains no valid JSON array")

    def _normalize_card(self, raw: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(raw, dict):
            return None

        front = str(raw.get("front", "")).strip()
        back = str(raw.get("back", "")).strip()
        if not front or not back:
            return None

        hint = str(raw.get("hint", "")).strip()
        tags = raw.get("tags")
        if not isinstance(tags, list):
            tags = []
        tags = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
        tags = tags[:3]

        return {
            "front": front,
            "back": back,
            "hint": hint,
            "tags": tags,
        }

    def generate(
        self, documents: List[Dict[str, Any]], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a deck of flashcards from the given documents.

        Args:
            documents: List of document dicts with name and text
            config: Flashcard config with num_cards and optional topic

        Returns:
            Dict with cards and config

        Raises:
            FlashcardGenerationError: If generation fails after retries
        """
        if not documents:
            raise FlashcardGenerationError("No documents provided")

        expected_count = int(config["num_cards"])
        last_error = None
        for _ in range(MAX_GENERATION_ATTEMPTS):
            try:
                prompt = self._build_prompt(documents, config)
                raw = self._call_llm(prompt)
                data = self._extract_json(raw)
                if isinstance(data, dict):
                    if "cards" not in data:
                        raise FlashcardGenerationError(
                            "LLM JSON object missing 'cards' key"
                        )
                    data = data["cards"]
                if not isinstance(data, list):
                    raise FlashcardGenerationError(
                        "LLM output must be a JSON array of cards"
                    )

                cards = []
                for item in data:
                    normalized = self._normalize_card(item)
                    if normalized is not None:
                        cards.append(normalized)

                if len(cards) < expected_count:
                    raise FlashcardGenerationError(
                        f"Expected {expected_count} cards, got {len(cards)}"
                    )
                if len(cards) > expected_count:
                    cards = cards[:expected_count]
                return {"cards": cards, "config": config}
            except FlashcardGenerationError as exc:
                last_error = exc

        raise FlashcardGenerationError(
            f"Flashcard generation failed after {MAX_GENERATION_ATTEMPTS} "
            f"attempts: {last_error}"
        )
