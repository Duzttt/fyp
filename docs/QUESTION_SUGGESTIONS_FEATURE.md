# Smart Question Suggestions Feature

## Overview

The Smart Question Suggestions feature automatically generates intelligent, context-aware question suggestions based on the user's selected documents. This helps users discover relevant questions and engage more effectively with their lecture notes.

## Features

### Frontend
- **Auto-generated suggestions**: 3 smart questions generated based on selected documents
- **One-click asking**: Click any suggestion to instantly ask the question
- **Loading states**: Visual feedback while generating suggestions
- **Refresh capability**: Manual refresh button to regenerate suggestions
- **Responsive design**: Beautiful gradient cards with hover effects
- **Fallback support**: Template-based suggestions if LLM is unavailable

### Backend
- **Hybrid generation approach**: 
  1. Keyword extraction using TF-IDF-like scoring
  2. Key phrase extraction from headers and noun phrases
  3. Template-based candidate generation
  4. LLM optimization for quality and diversity
- **Multiple question types**: Concept, method, comparison, reason, and example questions
- **Click tracking**: Analytics for suggestion usage
- **Diversity enforcement**: Avoids similar or duplicate questions

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      ChatPanel.vue                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            QuestionSuggestions.vue                    │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  💡 Suggested Questions                         │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │ 1. What is machine learning?              │  │  │  │
│  │  │  │ 2. How does it work?                      │  │  │  │
│  │  │  │ 3. Give an example                        │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    API Endpoints                            │
│  GET  /api/suggestions?doc_ids=[1,2,3]                     │
│  POST /api/suggestions/click                               │
│  GET  /api/suggestions/history                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              QuestionSuggestionService                      │
│  1. Extract keywords (TF-IDF)                              │
│  2. Extract key phrases                                     │
│  3. Generate candidate questions (templates)               │
│  4. Optimize with LLM (Qwen/Gemini/OpenRouter)            │
│  5. Select diverse final questions                          │
└─────────────────────────────────────────────────────────────┘
```

## API Reference

### Generate Suggestions

**Endpoint:** `GET /api/suggestions`

**Query Parameters:**
- `doc_ids` (required): Comma-separated list of document filenames
- `num_suggestions` (optional): Number of suggestions to generate (default: 3, max: 5)
- `llm_provider` (optional): LLM provider to use (default: "local_qwen")

**Response:**
```json
{
  "success": true,
  "suggestions": [
    "What is practical reasoning?",
    "How do intentions guide actions in AI systems?",
    "Compare subsumption architecture with classical planning"
  ],
  "generated_from": ["L4.1.pdf", "L5.1.pdf"],
  "document_count": 2
}
```

**Error Response:**
```json
{
  "detail": "No valid documents found in index"
}
```

### Record Suggestion Click

**Endpoint:** `POST /api/suggestions/click`

**Body:**
```json
{
  "question": "What is practical reasoning?",
  "doc_ids": ["L4.1.pdf", "L5.1.pdf"],
  "position": 0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Click recorded",
  "suggestion_id": 123,
  "click_count": 5
}
```

### Get Suggestion History

**Endpoint:** `GET /api/suggestions/history`

**Query Parameters:**
- `limit` (optional): Maximum number of suggestions to return (default: 20, max: 100)
- `doc_id` (optional): Filter by document ID

**Response:**
```json
{
  "suggestions": [
    {
      "id": 1,
      "question_text": "What is machine learning?",
      "question_type": "concept",
      "document_names": ["lecture1.pdf"],
      "click_count": 15,
      "feedback_score": null,
      "created_at": "2026-03-06T10:30:00Z"
    }
  ],
  "total": 1
}
```

## Usage

### Frontend Integration

The QuestionSuggestions component is already integrated into ChatPanel.vue:

```vue
<QuestionSuggestions
  :selected-documents="selectedDocuments"
  :disabled="isLoading"
  @question-select="handleSuggestionSelect"
/>
```

**Props:**
- `selectedDocuments`: Array of selected document objects
- `disabled`: Boolean to disable the component

**Events:**
- `question-select`: Emitted when a user clicks a suggestion, includes the question text

### Backend Service

```python
from app.services.question_suggestions import generate_question_suggestions

# Prepare documents
documents = [
    {
        "name": "lecture1.pdf",
        "content": "Machine learning is a subset of AI...",
    }
]

# Generate suggestions
result = generate_question_suggestions(documents, num_suggestions=3)

print(result["suggestions"])
# ["What is machine learning?", "How does ML work?", ...]
print(result["generated_from"])
# ["lecture1.pdf"]
```

## Question Types

The system generates diverse question types:

| Type | Description | Example |
|------|-------------|---------|
| **Concept** | Definition or explanation | "What is machine learning?" |
| **Method** | Process or implementation | "How does backpropagation work?" |
| **Comparison** | Differences between concepts | "What's the difference between supervised and unsupervised learning?" |
| **Reason** | Explanation of importance | "Why is regularization important?" |
| **Example** | Practical applications | "Can you give an example of clustering?" |

## Configuration

### LLM Provider

The system supports multiple LLM providers for question optimization:

```python
# Use local Qwen (default)
service = QuestionSuggestionService(llm_provider="local_qwen")

# Use Gemini
service = QuestionSuggestionService(llm_provider="gemini")

# Use OpenRouter
service = QuestionSuggestionService(llm_provider="openrouter")
```

### Fallback Behavior

If the LLM is unavailable, the system falls back to template-based selection:
- Selects questions from different types
- Ensures diversity using Jaccard similarity
- Keeps questions under 15 words

## Database Models

### SuggestedQuestion

```python
class SuggestedQuestion(models.Model):
    question_text = TextField()
    question_type = CharField(choices=[...])
    document_names = TextField()  # comma-separated
    click_count = IntegerField(default=0)
    feedback_score = FloatField(null=True)
    generation_metadata = JSONField()
    created_at = DateTimeField()
    updated_at = DateTimeField()
```

### Notebook (Optional)

```python
class Notebook(models.Model):
    name = CharField(max_length=255, unique=True)
    description = TextField(blank=True)
    document_names = TextField()  # comma-separated
    created_at = DateTimeField()
    updated_at = DateTimeField()
```

## Performance

- **Keyword extraction**: < 100ms for typical documents
- **Question generation**: < 500ms for 15 candidates
- **LLM optimization**: 1-3 seconds (depends on provider)
- **Total time**: Typically < 3 seconds

## Evaluation Metrics

Track these metrics for quality assessment:

- **Click-through rate (CTR)**: `clicks / impressions`
  - Target: > 20%
- **Question diversity**: Number of unique question types
  - Target: ≥ 2 types in 3 suggestions
- **Average question length**: Words per question
  - Target: 8-15 words
- **Generation success rate**: `successful generations / total requests`
  - Target: > 95%

## Troubleshooting

### No suggestions generated
1. Check that documents are selected
2. Verify documents are indexed in FAISS
3. Check backend logs for errors

### LLM timeout
- The system automatically falls back to template-based generation
- Consider increasing timeout in settings:
  ```python
  LOCAL_QWEN_TIMEOUT_SECONDS = 60  # Increase from default 30
  ```

### Poor quality suggestions
1. Ensure documents have sufficient text content
2. Check that keywords are being extracted correctly
3. Try a different LLM provider

## Testing

Run the test suite:

```bash
# Run all question suggestion tests
pytest tests/test_question_suggestions.py -v

# Run specific test category
pytest tests/test_question_suggestions.py::TestKeywordExtraction -v

# Run with coverage
pytest tests/test_question_suggestions.py --cov=app.services.question_suggestions
```

## Future Enhancements

- [ ] User feedback collection (thumbs up/down)
- [ ] Personalized suggestions based on user history
- [ ] Multi-language support
- [ ] Question difficulty levels
- [ ] Integration with quiz generation
- [ ] A/B testing for different generation strategies

## License

This feature is part of the Lecture Note Q&A System project.
