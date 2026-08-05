# Design Spec: HTML Presentation for Academic Defense

## Overview

A single, self-contained HTML presentation for defending the "AI-Based Lecture Note Q&A System Using RAG" project. Clean academic white theme, keyboard-navigable, portable across browsers.

## Requirements

- **Purpose**: Academic defense/viva presentation
- **Audience**: Academic committee / examiners
- **Style**: Balanced (technical depth + visual elements)
- **Slides**: 15-20 slides (18 planned)
- **Theme**: Clean academic white with blue accents
- **Format**: Single HTML file, no external dependencies (except Google Fonts)
- **Navigation**: Arrow keys, click, or touch swipe

## Slide Structure

### Section 1: Introduction & Motivation (Slides 1-3)

| # | Title | Content |
|---|-------|---------|
| 1 | Title Slide | Project name, presenter name, institution, date |
| 2 | Problem Statement | Challenges: manual PDF search, keyword-only matching, time-consuming navigation |
| 3 | Objectives | RAG pipeline, multi-provider LLM, FAISS vector search, intuitive UI |

### Section 2: Architecture Overview (Slides 4-6)

| # | Title | Content |
|---|-------|---------|
| 4 | System Overview | Architecture diagram: Frontend (Vue 3) → Django Backend → RAG Pipeline |
| 5 | Tech Stack | Table: Django 5.2, LangChain, Sentence Transformers, FAISS, Vue 3, TailwindCSS |
| 6 | RAG Pipeline Flow | Flowchart: PDF → Chunking → Embedding → FAISS → Query → Retrieval → LLM → Answer |

### Section 3: Implementation Details (Slides 7-10)

| # | Title | Content |
|---|-------|---------|
| 7 | PDF Processing | PDFLoader using PyPDFLoader, text extraction with page metadata |
| 8 | Text Chunking | RecursiveCharacterTextSplitter (400 chars, 50 overlap), sentence-aware splitting |
| 9 | Embeddings & Vector Store | all-MiniLM-L6-v2 (384-dim), FAISS IndexFlatL2, persistent index |
| 10 | LLM Integration | Gemini, OpenRouter, llama.cpp — flexibility, privacy, cost trade-offs |

### Section 4: Demo / Screenshots (Slides 11-13)

| # | Title | Content |
|---|-------|---------|
| 11 | UI Overview | Screenshot: Vue 3 dark glassmorphic interface |
| 12 | Upload Flow | Screenshot: PDF upload with drag-drop, indexing status |
| 13 | Chat Demo | Screenshot: Q&A with source citations and context display |

### Section 5: Evaluation Results (Slides 14-16)

| # | Title | Content |
|---|-------|---------|
| 14 | RAGAS Metrics | Table: faithfulness, answer_relevancy, context_precision, context_recall scores |
| 15 | Performance | Benchmarks: indexing speed, retrieval latency (<500ms), query throughput |
| 16 | Comparison | Baseline vs enhanced chunking/retrieval improvement percentages |

### Section 6: Limitations & Future Work + Conclusion (Slides 17-18)

| # | Title | Content |
|---|-------|---------|
| 17 | Limitations & Future | Current: text-only PDFs, single-server. Future: OCR, hybrid retrieval, multi-user |
| 18 | Conclusion | Summary, impact on learning efficiency, acknowledgments, Q&A |

## Technical Design

### File Structure

```
presentation/
└── index.html    # Single self-contained file
```

### HTML Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI-Based Lecture Note Q&A System</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@500;600;700&display=swap" rel="stylesheet">
  <style>/* All CSS embedded */</style>
</head>
<body>
  <div class="presentation">
    <section class="slide">...</section>
    <!-- 18 slides total -->
  </div>
  <script>/* Navigation logic */</script>
</body>
</html>
```

### CSS Design System

- **Background**: `#ffffff` (white)
- **Primary accent**: `#6366f1` (indigo, matching project theme)
- **Text primary**: `#1b1b1f` (near-black)
- **Text secondary**: `#44474f` (gray)
- **Headings**: Manrope font family
- **Body text**: Inter font family
- **Border radius**: 12px for cards, 8px for smaller elements
- **Shadows**: Subtle `box-shadow` for depth

### Navigation

- Arrow keys (← →) for slide navigation
- Click/tap on slide edges
- Slide counter indicator (e.g., "3 / 18")
- Smooth CSS transitions between slides

### Diagrams

- Architecture diagrams rendered as styled HTML/CSS (no images required)
- Flowcharts using flexbox layout with connecting lines via CSS borders
- Tables styled with alternating row colors

## Success Criteria

1. Presentation opens in any modern browser without errors
2. All 18 slides render correctly with proper typography
3. Keyboard navigation works (arrow keys)
4. Architecture diagrams are clear and readable
5. Screenshots display correctly (placeholder images if needed)
6. File is under 100KB total size
