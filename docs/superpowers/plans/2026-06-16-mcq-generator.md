# MCQ Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new MCQ (Multiple Choice Question) generation module to the Studio panel that generates questions with 4 answer options from selected lecture notes.

**Architecture:** Backend service follows the existing LLM-first pattern with template fallback. Frontend integrates into the Studio panel workflow with a modal for configuration and a viewer for results.

**Tech Stack:** Python/Django backend, Vue 3 frontend, LLM integration via Gemini/OpenRouter/llama.cpp

---

## File Structure

| File | Purpose |
|------|---------|
| `app/services/mcq_generator.py` | Core MCQ generation service |
| `django_app/views/mcq.py` | API endpoints for MCQ generation |
| `frontend/src/components/studio/MCQGenerator.vue` | MCQ generation modal |
| `frontend/src/components/studio/MCQViewer.vue` | MCQ display viewer |
| `frontend/src/stores/mcqStore.js` | State management for MCQ |
| `tests/test_mcq_generator.py` | Unit tests for MCQ service |

---

### Task 1: Backend MCQ Generator Service

**Files:**
- Create: `app/services/mcq_generator.py`
- Test: `tests/test_mcq_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcq_generator.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.mcq_generator import MCQGenerator, MCQGeneratorError


class TestMCQGenerator:
    """Tests for the MCQ Generator service."""

    def test_mcq_generator_initialization(self):
        """Test MCQGenerator initializes with default settings."""
        with patch('app.services.mcq_generator.load_runtime_llm_settings') as mock_rt:
            mock_rt.return_value = {
                'provider': 'local_llm',
                'model': 'test-model',
                'api_key': None,
                'base_url': None
            }
            generator = MCQGenerator()
            assert generator.llm_provider == 'local_llm'

    def test_parse_llm_response_valid(self):
        """Test parsing valid LLM response with MCQ format."""
        with patch('app.services.mcq_generator.load_runtime_llm_settings') as mock_rt:
            mock_rt.return_value = {
                'provider': 'local_llm',
                'model': 'test-model',
                'api_key': None,
                'base_url': None
            }
            generator = MCQGenerator()
            
            response = """Question 1: What is Python?
A) A programming language
B) A snake
C) A database
D) An operating system
Correct: A

Question 2: What does CPU stand for?
A) Central Processing Unit
B) Computer Personal Unit
C) Central Program Utility
D) Core Processing Unit
Correct: A"""
            
            mcqs = generator._parse_mcq_response(response, 2)
            assert len(mcqs) == 2
            assert mcqs[0]['question'] == 'What is Python?'
            assert len(mcqs[0]['options']) == 4
            assert mcqs[0]['correct_answer'] == 'A'

    def test_parse_llm_response_incomplete(self):
        """Test parsing incomplete MCQ response."""
        with patch('app.services.mcq_generator.load_runtime_llm_settings') as mock_rt:
            mock_rt.return_value = {
                'provider': 'local_llm',
                'model': 'test-model',
                'api_key': None,
                'base_url': None
            }
            generator = MCQGenerator()
            
            response = """Question 1: What is Python?
A) A programming language
B) A snake"""
            
            mcqs = generator._parse_mcq_response(response, 1)
            assert len(mcqs) == 0  # Incomplete options

    def test_generate_mcqs_empty_content(self):
        """Test generating MCQs from empty content raises error."""
        with patch('app.services.mcq_generator.load_runtime_llm_settings') as mock_rt:
            mock_rt.return_value = {
                'provider': 'local_llm',
                'model': 'test-model',
                'api_key': None,
                'base_url': None
            }
            generator = MCQGenerator()
            
            with pytest.raises(MCQGeneratorError):
                generator.generate_mcqs([])

    def test_build_mcq_prompt(self):
        """Test prompt construction for MCQ generation."""
        with patch('app.services.mcq_generator.load_runtime_llm_settings') as mock_rt:
            mock_rt.return_value = {
                'provider': 'local_llm',
                'model': 'test-model',
                'api_key': None,
                'base_url': None
            }
            generator = MCQGenerator()
            
            documents = [{'name': 'test.pdf', 'text': 'Python is a programming language.'}]
            prompt = generator._build_mcq_prompt(documents, 3)
            
            assert 'test.pdf' in prompt
            assert '3' in prompt
            assert 'A)' in prompt
            assert 'B)' in prompt
            assert 'C)' in prompt
            assert 'D)' in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcq_generator.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.mcq_generator'"

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/mcq_generator.py
"""
MCQ (Multiple Choice Question) Generator Service

Generates multiple choice questions with 4 answer options from lecture notes.
Uses LLM-first approach with validation.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.runtime_llm import load_runtime_llm_settings, resolve_gemini_api_model

logger = logging.getLogger(__name__)


class MCQGeneratorError(Exception):
    """Custom exception for MCQ generation errors."""
    pass


class MCQGenerator:
    """
    Service for generating multiple choice questions from document content.
    
    Uses LLM to generate MCQs with 4 answer options each.
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
        difficulty: str = "medium",
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        """
        Generate MCQs from document content.
        
        Args:
            documents: List of document dicts with name and text
            num_questions: Number of MCQs to generate
            difficulty: Difficulty level (easy, medium, hard)
            timeout_seconds: Maximum time for LLM response
            
        Returns:
            Dict with questions, document info, and metadata
        """
        if not documents:
            raise MCQGeneratorError("No documents provided")

        combined_text = self._combine_document_text(documents)
        if not combined_text.strip():
            raise MCQGeneratorError("Document content is empty")

        prompt = self._build_mcq_prompt(documents, num_questions, difficulty)
        response = self._call_llm(prompt, timeout_seconds)
        mcqs = self._parse_mcq_response(response, num_questions)

        if not mcqs:
            raise MCQGeneratorError("Failed to generate valid MCQs from LLM response")

        return {
            "questions": mcqs,
            "document_count": len(documents),
            "documents": [doc["name"] for doc in documents],
            "difficulty": difficulty,
            "total_questions": len(mcqs),
        }

    def _combine_document_text(self, documents: List[Dict[str, Any]]) -> str:
        """Combine text from multiple documents."""
        texts = []
        for doc in documents:
            name = doc.get("name", "Unknown")
            text = doc.get("text", "")
            if text:
                texts.append(f"=== {name} ===\n{text[:3000]}")
        return "\n\n".join(texts)

    def _build_mcq_prompt(
        self,
        documents: List[Dict[str, Any]],
        num_questions: int,
        difficulty: str = "medium",
    ) -> str:
        """Build prompt for MCQ generation."""
        doc_list = ", ".join(doc["name"] for doc in documents)
        
        difficulty_instruction = {
            "easy": "Basic recall and recognition questions.",
            "medium": "Questions requiring understanding and application.",
            "hard": "Questions requiring analysis, synthesis, or evaluation.",
        }.get(difficulty, "Questions requiring understanding and application.")

        return f"""You are an expert educator creating multiple choice questions for students.

Based on the following lecture notes from: {doc_list}

Generate EXACTLY {num_questions} multiple choice questions.

Difficulty Level: {difficulty_instruction}

FORMAT REQUIREMENTS (follow exactly):
- Each question must have exactly 4 options labeled A, B, C, D
- One option must be correct
- Include "Correct: X" after each question where X is the correct letter
- Distractors (wrong answers) should be plausible but clearly incorrect

OUTPUT FORMAT:
Question 1: [question text]
A) [option]
B) [option]
C) [option]
D) [option]
Correct: [letter]

Question 2: [question text]
A) [option]
B) [option]
C) [option]
D) [option]
Correct: [letter]

[Continue for all questions]

REQUIREMENTS:
- Questions must be answerable from the provided content
- Cover different topics from the lecture notes
- Each question tests a single concept
- Avoid double negatives or trick questions
- Make distractors realistic but unambiguous

Lecture Content:
{self._combine_document_text(documents)[:4000]}

Generate {num_questions} MCQs now:"""

    def _parse_mcq_response(self, response: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse LLM response to extract MCQs."""
        mcqs = []
        
        # Split by question pattern
        question_blocks = re.split(r'Question\s+\d+:', response)
        
        for block in question_blocks[1:]:  # Skip first empty split
            mcq = self._parse_single_mcq(block)
            if mcq and len(mcq.get("options", [])) == 4:
                mcqs.append(mcq)
        
        return mcqs[:expected_count]

    def _parse_single_mcq(self, block: str) -> Optional[Dict[str, Any]]:
        """Parse a single MCQ block."""
        lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Extract question (first line)
        question = lines[0].rstrip('?').strip() + '?'
        
        # Extract options
        options = []
        correct_answer = None
        
        for line in lines[1:]:
            # Match option pattern: A) text or A. text
            option_match = re.match(r'^([A-D])[\)\.]\s*(.+)', line)
            if option_match:
                letter = option_match.group(1)
                text = option_match.group(2).strip()
                options.append({"letter": letter, "text": text})
            
            # Match correct answer
            correct_match = re.match(r'^Correct:\s*([A-D])', line, re.IGNORECASE)
            if correct_match:
                correct_answer = correct_match.group(1).upper()
        
        if len(options) != 4 or not correct_answer:
            return None
        
        return {
            "question": question,
            "options": options,
            "correct_answer": correct_answer,
        }

    def _call_llm(self, prompt: str, timeout_seconds: int = 60) -> str:
        """Dispatch to the configured LLM provider."""
        if self.llm_provider == "local_llm":
            return self._call_local_llm(prompt, timeout_seconds)
        elif self.llm_provider == "gemini":
            return self._call_gemini(prompt, timeout_seconds)
        elif self.llm_provider == "openrouter":
            return self._call_openrouter(prompt, timeout_seconds)
        raise MCQGeneratorError(f"Unknown LLM provider: {self.llm_provider}")

    def _call_local_llm(self, prompt: str, timeout_seconds: int) -> str:
        """Call local LLM via llama.cpp."""
        try:
            from app.services.llm_client import call_llm
            return call_llm(
                provider="local_llm",
                model=self._runtime_model or settings.LOCAL_LLM_MODEL,
                call_type="mcq_generation",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                base_url=self._runtime_base_url or settings.LOCAL_LLM_BASE_URL,
                timeout=timeout_seconds,
            )
        except Exception as e:
            raise MCQGeneratorError(f"Local LLM call failed: {e}")

    def _call_gemini(self, prompt: str, timeout_seconds: int) -> str:
        """Call Gemini API."""
        try:
            from app.services.llm_client import call_llm
            api_key = self._runtime_api_key or settings.GEMINI_API_KEY
            if not api_key:
                raise MCQGeneratorError("GEMINI_API_KEY is not configured")
            return call_llm(
                provider="gemini",
                model=resolve_gemini_api_model(
                    self._runtime_model, settings.GEMINI_MODEL
                ),
                call_type="mcq_generation",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                api_key=api_key,
                base_url=self._runtime_base_url or settings.GEMINI_BASE_URL,
                temperature=0.7,
                max_tokens=2000,
            )
        except Exception as e:
            raise MCQGeneratorError(f"Gemini call failed: {e}")

    def _call_openrouter(self, prompt: str, timeout_seconds: int) -> str:
        """Call OpenRouter API."""
        try:
            from app.services.llm_client import call_llm
            api_key = self._runtime_api_key or settings.OPENROUTER_API_KEY
            if not api_key:
                raise MCQGeneratorError("OPENROUTER_API_KEY is not configured")
            return call_llm(
                provider="openrouter",
                model=self._runtime_model or settings.OPENROUTER_MODEL,
                call_type="mcq_generation",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                api_key=api_key,
                base_url=self._runtime_base_url or settings.OPENROUTER_BASE_URL,
                temperature=0.7,
                max_tokens=2000,
            )
        except Exception as e:
            raise MCQGeneratorError(f"OpenRouter call failed: {e}")


def get_mcq_generator(llm_provider: Optional[str] = None) -> MCQGenerator:
    """Get MCQ generator instance."""
    return MCQGenerator(llm_provider=llm_provider)


def generate_mcqs_from_documents(
    documents: List[Dict[str, Any]],
    num_questions: int = 5,
    difficulty: str = "medium",
    llm_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function to generate MCQs."""
    generator = get_mcq_generator(llm_provider=llm_provider)
    return generator.generate_mcqs(documents, num_questions, difficulty)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mcq_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/mcq_generator.py tests/test_mcq_generator.py
git commit -m "feat: add MCQ generator service with LLM integration"
```

---

### Task 2: Backend API View

**Files:**
- Create: `django_app/views/mcq.py`
- Modify: `django_app/views/__init__.py`
- Modify: `django_backend/urls.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcq_api.py
import json
import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory, TestCase
from django_app.views.mcq import generate_mcqs, get_mcq_history


class TestMCQAPI(TestCase):
    """Tests for MCQ API endpoints."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_generate_mcqs_missing_documents(self):
        """Test generate_mcqs returns error when no documents provided."""
        request = self.factory.post(
            '/api/mcq/generate',
            data=json.dumps({}),
            content_type='application/json'
        )
        response = generate_mcqs(request)
        assert response.status_code == 400

    def test_generate_mcqs_invalid_method(self):
        """Test generate_mcqs rejects GET requests."""
        request = self.factory.get('/api/mcq/generate')
        response = generate_mcqs(request)
        assert response.status_code == 405

    def test_get_mcq_history_returns_empty(self):
        """Test get_mcq_history returns empty list initially."""
        request = self.factory.get('/api/mcq/history')
        response = get_mcq_history(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'history' in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcq_api.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'django_app.views.mcq'"

- [ ] **Step 3: Write minimal implementation**

```python
# django_app/views/mcq.py
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django_app.views.helpers import _error_response, _get_json_body

MCQ_HISTORY_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "mcq_history.json"
)


def _load_mcq_history() -> List[Dict[str, Any]]:
    if not MCQ_HISTORY_FILE.exists():
        return []
    try:
        with MCQ_HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return []


def _save_mcq_history(history: List[Dict[str, Any]]) -> None:
    MCQ_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with MCQ_HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _get_document_text(filename: str) -> Optional[str]:
    from app.config import settings
    from app.services.runtime_embedding import load_runtime_embedding_settings
    from app.services.vector_store import VectorStore

    try:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )
        doc_chunks = []
        for chunk in vector_store.chunks:
            chunk_source = str(chunk.get("source", ""))
            if filename in chunk_source or chunk_source.endswith(filename):
                doc_chunks.append(chunk)
        if not doc_chunks:
            return None
        doc_chunks.sort(key=lambda c: c.get("page", 0) or 0)
        return " ".join([str(c.get("text", "")) for c in doc_chunks])
    except Exception:
        return None


@csrf_exempt
@require_http_methods(["POST"])
def generate_mcqs(request: HttpRequest) -> JsonResponse:
    from app.services.mcq_generator import MCQGenerator, MCQGeneratorError

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    document_ids = payload.get("document_ids", [])
    num_questions = payload.get("num_questions", 5)
    difficulty = payload.get("difficulty", "medium")

    if not document_ids:
        return _error_response("No documents selected", status=400)

    if not isinstance(document_ids, list):
        return _error_response("document_ids must be a list", status=400)

    num_questions = min(max(1, num_questions), 10)

    documents = []
    for doc_id in document_ids:
        text = _get_document_text(doc_id)
        if text:
            documents.append({"name": doc_id, "text": text})

    if not documents:
        return _error_response("No valid documents found", status=404)

    try:
        generator = MCQGenerator()
        result = generator.generate_mcqs(documents, num_questions, difficulty)

        history = _load_mcq_history()
        history_entry = {
            "id": f"mcq_{int(time.time())}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "documents": [doc["name"] for doc in documents],
            "questions": result["questions"],
            "difficulty": difficulty,
            "document_count": len(documents),
        }
        history.insert(0, history_entry)
        if len(history) > 50:
            history = history[:50]
        _save_mcq_history(history)

        return JsonResponse({
            "success": True,
            "questions": result["questions"],
            "document_count": len(documents),
            "documents": [doc["name"] for doc in documents],
            "difficulty": difficulty,
            "total_questions": len(result["questions"]),
            "history_id": history_entry["id"],
        })

    except MCQGeneratorError as exc:
        return _error_response(str(exc), status=500)
    except Exception as exc:
        return _error_response(f"Failed to generate MCQs: {str(exc)}", status=500)


@require_http_methods(["GET"])
def get_mcq_history(request: HttpRequest) -> JsonResponse:
    try:
        limit = int(request.GET.get("limit", 20))
        limit = min(limit, 50)
        history = _load_mcq_history()
        return JsonResponse({
            "history": history[:limit],
            "total": len(history),
        })
    except Exception as exc:
        return _error_response(f"Failed to load history: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_mcq(request: HttpRequest, mcq_id: str) -> JsonResponse:
    try:
        history = _load_mcq_history()
        new_history = [h for h in history if h.get("id") != mcq_id]
        if len(new_history) == len(history):
            return _error_response("MCQ not found", status=404)
        _save_mcq_history(new_history)
        return JsonResponse({"success": True, "message": "MCQ deleted"})
    except Exception as exc:
        return _error_response(f"Failed to delete MCQ: {str(exc)}", status=500)
```

- [ ] **Step 4: Update views/__init__.py**

Add to `django_app/views/__init__.py`:
```python
from django_app.views.mcq import generate_mcqs, get_mcq_history, delete_mcq
```

- [ ] **Step 5: Update urls.py**

Add to `django_backend/urls.py`:
```python
# MCQ Generation endpoints
path("api/mcq/generate", views.generate_mcqs),
path("api/mcq/generate/", views.generate_mcqs),
path("api/mcq/history", views.get_mcq_history),
path("api/mcq/history/", views.get_mcq_history),
path("api/mcq/<str:mcq_id>/delete", views.delete_mcq),
path("api/mcq/<str:mcq_id>/delete/", views.delete_mcq),
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_mcq_api.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add django_app/views/mcq.py django_app/views/__init__.py django_backend/urls.py tests/test_mcq_api.py
git commit -m "feat: add MCQ API endpoints for generation and history"
```

---

### Task 3: Frontend State Management

**Files:**
- Create: `frontend/src/stores/mcqStore.js`

- [ ] **Step 1: Create mcqStore.js**

```javascript
// frontend/src/stores/mcqStore.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export const useMCQStore = defineStore('mcq', () => {
  const questions = ref([])
  const history = ref([])
  const isGenerating = ref(false)
  const currentMCQ = ref(null)
  const lastConfig = ref(null)
  const error = ref(null)

  const questionCount = computed(() => questions.value.length)
  const hasQuestions = computed(() => questions.value.length > 0)

  async function generate(documentIds, config = {}) {
    isGenerating.value = true
    error.value = null
    
    try {
      const payload = {
        document_ids: documentIds,
        num_questions: config.num_questions || 5,
        difficulty: config.difficulty || 'medium',
      }
      
      const response = await api.post('/api/mcq/generate', payload)
      
      if (response.data.success) {
        questions.value = response.data.questions
        currentMCQ.value = response.data
        lastConfig.value = config
        return response.data
      } else {
        throw new Error(response.data.error || 'Failed to generate MCQs')
      }
    } catch (err) {
      error.value = err.message || 'Failed to generate MCQs'
      throw err
    } finally {
      isGenerating.value = false
    }
  }

  async function loadHistory(limit = 20) {
    try {
      const response = await api.get(`/api/mcq/history?limit=${limit}`)
      history.value = response.data.history || []
    } catch (err) {
      console.error('Failed to load MCQ history:', err)
    }
  }

  async function deleteMCQ(mcqId) {
    try {
      await api.post(`/api/mcq/${mcqId}/delete`)
      history.value = history.value.filter(h => h.id !== mcqId)
    } catch (err) {
      console.error('Failed to delete MCQ:', err)
    }
  }

  function clearCurrent() {
    questions.value = []
    currentMCQ.value = null
    error.value = null
  }

  return {
    questions,
    history,
    isGenerating,
    currentMCQ,
    lastConfig,
    error,
    questionCount,
    hasQuestions,
    generate,
    loadHistory,
    deleteMCQ,
    clearCurrent,
  }
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/stores/mcqStore.js
git commit -m "feat: add MCQ store for state management"
```

---

### Task 4: Frontend MCQ Generator Modal

**Files:**
- Create: `frontend/src/components/studio/MCQGenerator.vue`

- [ ] **Step 1: Create MCQGenerator.vue**

```vue
<!-- frontend/src/components/studio/MCQGenerator.vue -->
<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  show: Boolean,
  selectedDocs: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['generate', 'close'])

const numQuestions = ref(5)
const difficulty = ref('medium')

const difficulties = [
  { value: 'easy', label: 'Easy', desc: 'Basic recall questions' },
  { value: 'medium', label: 'Medium', desc: 'Understanding & application' },
  { value: 'hard', label: 'Hard', desc: 'Analysis & synthesis' },
]

const canGenerate = computed(() => {
  return props.selectedDocs.length > 0 && numQuestions.value >= 1 && numQuestions.value <= 10
})

const handleGenerate = () => {
  if (!canGenerate.value) return
  emit('generate', {
    num_questions: numQuestions.value,
    difficulty: difficulty.value,
  })
}

const handleClose = () => {
  emit('close')
}
</script>

<template>
  <div v-if="show" class="modal-overlay" @click.self="handleClose">
    <div class="modal-content">
      <div class="modal-header">
        <h3>Generate MCQs</h3>
        <button type="button" class="close-btn" @click="handleClose" aria-label="Close">
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <div class="selected-docs">
          <span class="label">Selected Documents:</span>
          <span class="count">{{ selectedDocs.length }} file(s)</span>
        </div>

        <div class="form-group">
          <label for="numQuestions">Number of Questions</label>
          <input
            id="numQuestions"
            v-model.number="numQuestions"
            type="number"
            min="1"
            max="10"
            class="input-field"
          />
        </div>

        <div class="form-group">
          <label>Difficulty Level</label>
          <div class="difficulty-options">
            <button
              v-for="d in difficulties"
              :key="d.value"
              type="button"
              class="difficulty-btn"
              :class="{ active: difficulty === d.value }"
              @click="difficulty = d.value"
            >
              <span class="diff-label">{{ d.label }}</span>
              <span class="diff-desc">{{ d.desc }}</span>
            </button>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn-cancel" @click="handleClose">Cancel</button>
        <button
          type="button"
          class="btn-generate"
          :disabled="!canGenerate"
          @click="handleGenerate"
        >
          Generate MCQs
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface-container);
  border-radius: 16px;
  width: 90%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--outline-variant);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--on-surface);
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-surface-variant);
}

.close-btn:hover {
  background: var(--surface-container-high);
}

.modal-body {
  padding: 20px;
}

.selected-docs {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  padding: 12px;
  background: var(--surface-container-high);
  border-radius: 8px;
}

.selected-docs .label {
  font-size: 13px;
  color: var(--on-surface-variant);
}

.selected-docs .count {
  font-weight: 600;
  color: var(--primary);
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--on-surface);
  margin-bottom: 8px;
}

.input-field {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--outline-variant);
  border-radius: 8px;
  background: var(--surface-container-low);
  color: var(--on-surface);
  font-size: 14px;
}

.input-field:focus {
  outline: none;
  border-color: var(--primary);
}

.difficulty-options {
  display: flex;
  gap: 8px;
}

.difficulty-btn {
  flex: 1;
  padding: 12px 8px;
  border: 2px solid var(--outline-variant);
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;
}

.difficulty-btn:hover {
  border-color: var(--primary);
}

.difficulty-btn.active {
  border-color: var(--primary);
  background: var(--primary-container);
}

.diff-label {
  display: block;
  font-weight: 600;
  font-size: 13px;
  color: var(--on-surface);
}

.diff-desc {
  display: block;
  font-size: 11px;
  color: var(--on-surface-variant);
  margin-top: 4px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--outline-variant);
}

.btn-cancel {
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--on-surface-variant);
  font-weight: 500;
  cursor: pointer;
}

.btn-cancel:hover {
  background: var(--surface-container-high);
}

.btn-generate {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  background: var(--primary);
  color: var(--on-primary);
  font-weight: 600;
  cursor: pointer;
}

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-generate:not(:disabled):hover {
  background: var(--primary-container);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studio/MCQGenerator.vue
git commit -m "feat: add MCQ generator modal component"
```

---

### Task 5: Frontend MCQ Viewer

**Files:**
- Create: `frontend/src/components/studio/MCQViewer.vue`

- [ ] **Step 1: Create MCQViewer.vue**

```vue
<!-- frontend/src/components/studio/MCQViewer.vue -->
<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  questions: {
    type: Array,
    default: () => [],
  },
  config: {
    type: Object,
    default: () => ({}),
  },
  isLoading: Boolean,
})

const emit = defineEmits(['regenerate', 'close'])

const currentQuestionIndex = ref(0)
const selectedAnswers = ref({})
const showAnswers = ref(false)

const currentQuestion = computed(() => {
  return props.questions[currentQuestionIndex.value] || null
})

const totalQuestions = computed(() => props.questions.length)

const progress = computed(() => {
  if (totalQuestions.value === 0) return 0
  return ((currentQuestionIndex.value + 1) / totalQuestions.value) * 100
})

const isCorrect = computed(() => {
  if (!currentQuestion.value) return null
  return selectedAnswers.value[currentQuestionIndex.value] === currentQuestion.value.correct_answer
})

const selectAnswer = (letter) => {
  selectedAnswers.value[currentQuestionIndex.value] = letter
  showAnswers.value = true
}

const nextQuestion = () => {
  if (currentQuestionIndex.value < totalQuestions.value - 1) {
    currentQuestionIndex.value++
    showAnswers.value = false
  }
}

const prevQuestion = () => {
  if (currentQuestionIndex.value > 0) {
    currentQuestionIndex.value--
    showAnswers.value = selectedAnswers.value[currentQuestionIndex.value] !== undefined
  }
}

const resetQuiz = () => {
  currentQuestionIndex.value = 0
  selectedAnswers.value = {}
  showAnswers.value = false
}

const score = computed(() => {
  let correct = 0
  props.questions.forEach((q, idx) => {
    if (selectedAnswers.value[idx] === q.correct_answer) {
      correct++
    }
  })
  return correct
})
</script>

<template>
  <div class="mcq-viewer">
    <div v-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Generating MCQs...</p>
    </div>

    <div v-else-if="questions.length === 0" class="empty-state">
      <p>No questions generated yet.</p>
    </div>

    <div v-else class="quiz-container">
      <div class="quiz-header">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <div class="progress-text">
          Question {{ currentQuestionIndex + 1 }} of {{ totalQuestions }}
        </div>
      </div>

      <div class="question-card">
        <h4 class="question-text">{{ currentQuestion?.question }}</h4>
        
        <div class="options-list">
          <button
            v-for="option in currentQuestion?.options"
            :key="option.letter"
            type="button"
            class="option-btn"
            :class="{
              selected: selectedAnswers[currentQuestionIndex] === option.letter,
              correct: showAnswers && option.letter === currentQuestion.correct_answer,
              incorrect: showAnswers && selectedAnswers[currentQuestionIndex] === option.letter && option.letter !== currentQuestion.correct_answer,
            }"
            :disabled="showAnswers"
            @click="selectAnswer(option.letter)"
          >
            <span class="option-letter">{{ option.letter }}</span>
            <span class="option-text">{{ option.text }}</span>
          </button>
        </div>

        <div v-if="showAnswers" class="answer-feedback" :class="{ correct: isCorrect, incorrect: !isCorrect }">
          <span v-if="isCorrect">✓ Correct!</span>
          <span v-else>✗ Incorrect. The answer is: {{ currentQuestion.correct_answer }}</span>
        </div>
      </div>

      <div class="quiz-nav">
        <button
          type="button"
          class="nav-btn"
          :disabled="currentQuestionIndex === 0"
          @click="prevQuestion"
        >
          Previous
        </button>
        
        <button
          v-if="currentQuestionIndex < totalQuestions - 1"
          type="button"
          class="nav-btn primary"
          @click="nextQuestion"
        >
          Next
        </button>
        
        <button
          v-else
          type="button"
          class="nav-btn primary"
          @click="resetQuiz"
        >
          Restart
        </button>
      </div>

      <div v-if="score > 0 || Object.keys(selectedAnswers).length === totalQuestions" class="score-summary">
        Score: {{ score }} / {{ totalQuestions }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.mcq-viewer {
  padding: 16px;
}

.loading-state, .empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--on-surface-variant);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--outline-variant);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.quiz-header {
  margin-bottom: 20px;
}

.progress-bar {
  height: 6px;
  background: var(--surface-container-high);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: var(--on-surface-variant);
  text-align: center;
}

.question-card {
  background: var(--surface-container);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.question-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0 0 16px 0;
  line-height: 1.4;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.option-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 2px solid var(--outline-variant);
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.option-btn:hover:not(:disabled) {
  border-color: var(--primary);
  background: var(--primary-container);
}

.option-btn.selected {
  border-color: var(--primary);
  background: var(--primary-container);
}

.option-btn.correct {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
}

.option-btn.incorrect {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.option-letter {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--surface-container-high);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  color: var(--on-surface);
  flex-shrink: 0;
}

.option-btn.selected .option-letter {
  background: var(--primary);
  color: var(--on-primary);
}

.option-text {
  font-size: 14px;
  color: var(--on-surface);
}

.answer-feedback {
  margin-top: 16px;
  padding: 12px;
  border-radius: 8px;
  font-weight: 500;
  text-align: center;
}

.answer-feedback.correct {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.answer-feedback.incorrect {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.quiz-nav {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.nav-btn {
  flex: 1;
  padding: 12px 16px;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  background: var(--surface-container-high);
  color: var(--on-surface);
}

.nav-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.nav-btn.primary {
  background: var(--primary);
  color: var(--on-primary);
}

.nav-btn.primary:hover:not(:disabled) {
  opacity: 0.9;
}

.score-summary {
  margin-top: 16px;
  text-align: center;
  font-size: 18px;
  font-weight: 600;
  color: var(--primary);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studio/MCQViewer.vue
git commit -m "feat: add MCQ viewer component with quiz interface"
```

---

### Task 6: Update StudioPanel.vue

**Files:**
- Modify: `frontend/src/components/layout/StudioPanel.vue`

- [ ] **Step 1: Add MCQ tool to StudioPanel**

Update `StudioPanel.vue` to include the MCQ generator:

```vue
<script setup>
import { ref, computed } from 'vue'
import { useDocumentStore } from '../../stores/documentStore'
import { useSummaryStore } from '../../stores/summaryStore'
import { useMCQStore } from '../../stores/mcqStore'
import SummaryModal from '../studio/SummaryModal.vue'
import SummaryViewer from '../studio/SummaryViewer.vue'
import MCQGenerator from '../studio/MCQGenerator.vue'
import MCQViewer from '../studio/MCQViewer.vue'

const documentStore = useDocumentStore()
const summaryStore = useSummaryStore()
const mcqStore = useMCQStore()

const studioTools = [
  {
    id: 'summary',
    title: 'Summarize PDF',
    desc: 'Condense complex papers into high-level editorial abstracts.',
    icon: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z',
    action: 'summary',
  },
  {
    id: 'mcq',
    title: 'Generate MCQs',
    desc: 'Create multiple choice questions from lecture notes.',
    icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z',
    action: 'mcq',
  },
]

const showSummaryModal = ref(false)
const showSummaryViewer = ref(false)
const showMCQGenerator = ref(false)
const showMCQViewer = ref(false)

const selectedDocs = computed(() => documentStore.selectedDocIds)
const selectedCount = computed(() => selectedDocs.value.length)
const currentSummary = computed(() => summaryStore.currentSummary)
const isGenerating = computed(() => summaryStore.isGenerating)
const mcqQuestions = computed(() => mcqStore.questions)
const isGeneratingMCQ = computed(() => mcqStore.isGenerating)

const handleToolClick = (tool) => {
  if (tool.disabled) return
  if (tool.action === 'summary') {
    openSummaryModal()
  } else if (tool.action === 'mcq') {
    openMCQGenerator()
  }
}

const openSummaryModal = () => {
  if (selectedCount.value === 0) {
    alert('Please select at least one document in the sidebar first')
    return
  }
  showSummaryModal.value = true
}

const openMCQGenerator = () => {
  if (selectedCount.value === 0) {
    alert('Please select at least one document in the sidebar first')
    return
  }
  showMCQGenerator.value = true
}

const handleSummaryGenerate = async (config) => {
  await summaryStore.generate(selectedDocs.value, config)
  showSummaryModal.value = false
  showSummaryViewer.value = true
}

const handleSummaryRegenerate = async () => {
  if (currentSummary.value?.history_id) {
    const newConfig = summaryStore.lastConfig || {}
    await summaryStore.regenerate(currentSummary.value.history_id, newConfig)
  }
}

const handleSummaryFeedback = (rating) => {
  console.log('Feedback:', rating)
}

const closeSummaryViewer = () => {
  showSummaryViewer.value = false
  summaryStore.clearCurrent()
}

const handleMCQGenerate = async (config) => {
  await mcqStore.generate(selectedDocs.value, config)
  showMCQGenerator.value = false
  showMCQViewer.value = true
}

const handleMCQRegenerate = () => {
  showMCQViewer.value = false
  showMCQGenerator.value = true
}

const closeMCQViewer = () => {
  showMCQViewer.value = false
  mcqStore.clearCurrent()
}
</script>

<template>
  <div class="panel studio-panel">
    <div class="panel-header">
      <h2 class="panel-title">Studio Tools</h2>
    </div>

    <div class="panel-body">
      <div class="tools-list">
        <button
          v-for="tool in studioTools"
          :key="tool.id"
          type="button"
          class="tool-card"
          :class="{ disabled: tool.disabled }"
          :disabled="tool.disabled"
          @click="handleToolClick(tool)"
        >
          <div class="tool-icon-wrap">
            <svg class="tool-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path :d="tool.icon" /></svg>
          </div>
          <div class="tool-content">
            <span class="tool-title">{{ tool.title }}</span>
            <span class="tool-desc">{{ tool.desc }}</span>
          </div>
          <span v-if="tool.action === 'summary' && selectedCount > 0" class="tool-badge" aria-hidden="true">
            {{ selectedCount }}
          </span>
          <span v-if="tool.action === 'mcq' && selectedCount > 0" class="tool-badge" aria-hidden="true">
            {{ selectedCount }}
          </span>
        </button>
      </div>

      <div v-if="showSummaryViewer" class="summary-viewer-container">
        <div class="viewer-header">
          <span class="viewer-title">Summary</span>
          <button type="button" class="viewer-close" aria-label="Close summary" @click="closeSummaryViewer">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
          </button>
        </div>
        <SummaryViewer
          :summary="currentSummary"
          :config="summaryStore.lastConfig"
          :is-loading="isGenerating"
          @regenerate="handleSummaryRegenerate"
          @feedback="handleSummaryFeedback"
        />
      </div>

      <div v-if="showMCQViewer" class="mcq-viewer-container">
        <div class="viewer-header">
          <span class="viewer-title">MCQ Quiz</span>
          <button type="button" class="viewer-close" aria-label="Close MCQ" @click="closeMCQViewer">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
          </button>
        </div>
        <MCQViewer
          :questions="mcqQuestions"
          :config="mcqStore.lastConfig"
          :is-loading="isGeneratingMCQ"
          @regenerate="handleMCQRegenerate"
        />
      </div>

    </div>

    <SummaryModal
      v-model:show="showSummaryModal"
      :selected-docs="selectedDocs"
      @generate="handleSummaryGenerate"
      @close="showSummaryModal = false"
    />

    <MCQGenerator
      :show="showMCQGenerator"
      :selected-docs="selectedDocs"
      @generate="handleMCQGenerate"
      @close="showMCQGenerator = false"
    />
  </div>
</template>

<style scoped>
/* Add MCQ viewer container styles */
.mcq-viewer-container {
  border-radius: 10px;
  background: var(--surface-container);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 500px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/layout/StudioPanel.vue
git commit -m "feat: integrate MCQ generator into Studio panel"
```

---

### Task 7: Final Verification

**Files:**
- Run: `pytest tests/test_mcq_generator.py tests/test_mcq_api.py -v`
- Run: `ruff check app/services/mcq_generator.py django_app/views/mcq.py`

- [ ] **Step 1: Run all tests**

```bash
pytest tests/test_mcq_generator.py tests/test_mcq_api.py -v
```

Expected: All tests pass

- [ ] **Step 2: Run linting**

```bash
ruff check app/services/mcq_generator.py django_app/views/mcq.py
```

Expected: No errors

- [ ] **Step 3: Run type checking**

```bash
mypy app/services/mcq_generator.py django_app/views/mcq.py
```

Expected: No errors

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: MCQ generator module complete with tests and linting"
```

---

## Summary

This plan adds an MCQ generation module with:
- Backend service using LLM-first approach
- API endpoints for generation and history
- Frontend components: modal for configuration, viewer for quiz interface
- Integration into Studio panel workflow
- Comprehensive tests and linting
