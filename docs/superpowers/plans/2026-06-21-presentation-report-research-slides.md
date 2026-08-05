# Presentation Report Research Slides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise the existing HTML presentation into an evidence-based 18-slide academic-defense deck containing a strengthened problem statement, measurable objectives, project scope, the top three ranked studies, a methodology flowchart, and a graph calculated from the project's RAGAS CSV results.

**Architecture:** Keep the presentation as one portable HTML file with embedded CSS and JavaScript. Add small semantic CSS components for research cards, scope columns, the six-stage methodology, and a dependency-free grouped bar chart; protect the narrative and evidence with a focused pytest structure test, then verify navigation and slide layout in a real browser.

**Tech Stack:** HTML5, CSS Grid/Flexbox, vanilla JavaScript, pytest, Python standard library, repository JSON/CSV evidence, and in-app browser inspection.

---

## File Structure

- Modify: `presentation/index.html`
  - Remains the only runtime presentation artifact.
  - Contains all 18 slides, styles, chart values, and existing navigation code.
- Create: `tests/test_presentation_report.py`
  - Verifies the approved slide sequence, required evidence, graph values, and removal of unsupported legacy claims.
- Read only: `tmp/report_build/literature_evidence.json`
  - Source-verified evidence for the three highest-ranked studies.
- Read only: `eval_baseline_result.csv`
- Read only: `eval_baseline_result_after_smartchunker.csv`
- Read only: `eval_baseline_result_after_retrieaval.csv`
  - Comparable 25-question RAGAS evaluation files used for the graph.
- Read only: `app/services/pdf_indexing.py`, `app/services/pdf_chunking.py`, `retrieval/hybrid_retriever.py`, `app/services/local_rag.py`
  - Current implementation evidence for the technical and methodology slides.

## Evidence Locked for Implementation

Use these verified literature records:

1. **Alawwad et al. (2025)** — “Enhancing textual textbook question answering with large language models and retrieval augmented generation”; fine-tuned Llama-2 with semantic retrieval; 84.24% textual TQA test accuracy; limited to text and does not integrate diagrams; DOI `10.1016/j.patcog.2024.111332`.
2. **Hu et al. (2025)** — “ICCA-RAG: Intelligent Customs Clearance Assistant Using Retrieval-Augmented Generation”; multimodal parsing with sparse-dense hybrid retrieval and LLM generation; reported improvements of 20.1% correctness, 15.3% relevancy, and 18.7% faithfulness; real-time retrieval at scale still needs optimization; DOI `10.1109/ACCESS.2025.3544408`.
3. **Neumann et al. (2024)** — “An LLM-Driven Chatbot in Higher Education for Databases and Information Systems”; GPT-4 RAG chatbot integrated into Moodle with LangChain and Weaviate; 88% response accuracy; students still preferred human tutors and automated fact-checking was weak; DOI `10.1109/TE.2024.3467912`.

Use these RAGAS means, recalculated from 25 identical question/reference rows in each file:

| Series | Faithfulness | Answer relevancy | Context precision | Context recall |
|---|---:|---:|---:|---:|
| Original baseline | 0.85 | 0.86 | 0.67 | 0.84 |
| Smart chunking run | 0.59 | 0.60 | 0.29 | 0.24 |
| Enhanced retrieval run | 0.65 | 0.80 | 0.53 | 0.58 |

The graph must describe observed scores, not claim that every later run improved on the original baseline. The evidence-based interpretation is that enhanced retrieval recovered substantial quality relative to the smart-chunking run, while the original baseline remained strongest overall in this evaluation.

### Task 1: Add Presentation Contract Tests

**Files:**
- Create: `tests/test_presentation_report.py`
- Read: `presentation/index.html`

- [ ] **Step 1: Write the presentation structure and evidence tests**

Create `tests/test_presentation_report.py` with:

```python
import html
import re
from pathlib import Path
from typing import List


PRESENTATION_PATH = Path(__file__).parents[1] / "presentation" / "index.html"
SLIDE_PATTERN = re.compile(
    r'<section class="slide(?: active)?">(.*?)</section>', re.DOTALL
)


def _presentation_html() -> str:
    return PRESENTATION_PATH.read_text(encoding="utf-8")


def _slides() -> List[str]:
    return SLIDE_PATTERN.findall(_presentation_html())


def _plain_text(fragment: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(without_tags).split())


def test_presentation_contains_approved_18_slide_sequence() -> None:
    expected_headings = [
        "AI-Based Lecture Note Question Answering System",
        "Problem Statement",
        "Project Objectives",
        "Project Scope and Boundaries",
        "Literature Review — Top Three Studies",
        "Research Gap and Project Contribution",
        "Methodology",
        "System Architecture and Technology Stack",
        "PDF Ingestion and Indexing",
        "Retrieval and Answer-Generation Flow",
        "Core Technical Design",
        "Interface and User Workflow",
        "Chat Demonstration",
        "Evaluation Method — RAGAS",
        "RAGAS Results",
        "Findings and Discussion",
        "Limitations and Future Work",
        "Conclusion",
    ]
    slide_text = [_plain_text(slide) for slide in _slides()]
    assert len(slide_text) == 18
    assert all(
        expected in actual
        for expected, actual in zip(expected_headings, slide_text)
    )


def test_research_slides_include_required_scope_and_methodology() -> None:
    source = _presentation_html()
    required_phrases = [
        "In scope",
        "Out of scope",
        "Project and Problem Understanding",
        "Lecture-Note Data Understanding",
        "PDF Extraction and Text Preparation",
        "RAG Modelling and Application Development",
        "Technical and Functional Evaluation",
        "Deployment and Iterative Refinement",
    ]
    assert all(phrase in source for phrase in required_phrases)


def test_literature_slide_uses_verified_top_three_studies() -> None:
    source = _presentation_html()
    expected = [
        ('data-study-rank="1"', "Alawwad et al. (2025)", "84.24%"),
        ('data-study-rank="2"', "Hu et al. (2025)", "20.1%"),
        ('data-study-rank="3"', "Neumann et al. (2024)", "88%"),
    ]
    for rank_attribute, citation, result in expected:
        assert rank_attribute in source
        assert citation in source
        assert result in source


def test_results_graph_embeds_recalculated_ragas_means() -> None:
    source = _presentation_html()
    expected_attributes = [
        'data-series="baseline" data-values="0.85,0.86,0.67,0.84"',
        'data-series="smart-chunking" data-values="0.59,0.60,0.29,0.24"',
        'data-series="enhanced-retrieval" data-values="0.65,0.80,0.53,0.58"',
    ]
    assert all(attribute in source for attribute in expected_attributes)
    assert "25 identical question/reference pairs" in source


def test_unsupported_legacy_claims_are_removed() -> None:
    source = _presentation_html()
    unsupported_claims = [
        "150 lecture PDFs",
        "1,800 pages",
        "12 pages/sec",
        "320 ms",
        "+16.7% improvement",
        "Hybrid retrieval combining BM25 and dense vectors",
    ]
    assert all(claim not in source for claim in unsupported_claims)


def test_navigation_uses_computed_slide_count() -> None:
    source = _presentation_html()
    assert "var total = slides.length;" in source
    assert "totalEl.textContent = total;" in source
    assert '<span id="total">18</span>' in source
```

- [ ] **Step 2: Run the new tests and verify the research contract fails**

Run:

```powershell
pytest tests/test_presentation_report.py -v --tb=short
```

Expected: at least the sequence, scope/methodology, literature, graph, and unsupported-claims tests fail against the current deck. The computed navigation test should pass.

- [ ] **Step 3: Commit the failing contract test**

```powershell
git add tests/test_presentation_report.py
git commit -m "test: define presentation research slide contract"
```

### Task 2: Add Reusable Research-Slide Styles

**Files:**
- Modify: `presentation/index.html` inside the existing `<style>` block before its responsive media query.
- Test: `tests/test_presentation_report.py`

- [ ] **Step 1: Add exact styles for scope, literature, gap, methodology, and chart components**

Insert these component families into the existing stylesheet, preserving the existing color variables:

```css
.scope-grid,
.evidence-grid,
.gap-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.scope-card,
.gap-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 22px;
}
.scope-card.in-scope { border-top: 3px solid #6b8a7a; }
.scope-card.out-scope { border-top: 3px solid var(--accent); }
.scope-card h3,
.gap-card h3 { font-size: 17px; margin-bottom: 10px; }
.scope-list { list-style: none; display: grid; gap: 7px; }
.scope-list li {
  position: relative;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}
.scope-list li::before {
  content: "✓";
  position: absolute;
  left: 0;
  color: #6b8a7a;
  font-weight: 700;
}
.out-scope .scope-list li::before { content: "—"; color: var(--accent); }
.evidence-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.evidence-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-top: 3px solid var(--accent);
  border-radius: var(--radius);
  padding: 18px;
  min-height: 270px;
}
.evidence-rank {
  font-family: var(--font-mono);
  color: var(--accent);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.evidence-card h3 { font-size: 15px; margin: 7px 0 10px; }
.evidence-line { margin-top: 8px; font-size: 12px; line-height: 1.45; color: var(--text-secondary); }
.evidence-line strong { color: var(--text); }
.citation-line { margin-top: 10px; font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); }
.gap-card.contribution { background: var(--accent-soft); border-color: #f3d5a3; }
.gap-arrow {
  display: flex;
  justify-content: center;
  align-items: center;
  color: var(--accent);
  font-size: 26px;
  margin: 12px 0;
}
.methodology-flow {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 9px;
  align-items: stretch;
}
.method-stage {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-top: 3px solid var(--accent);
  border-radius: var(--radius-sm);
  padding: 16px 10px 13px;
  min-height: 152px;
  text-align: center;
}
.method-stage:not(:last-child)::after {
  content: "→";
  position: absolute;
  right: -11px;
  top: 62px;
  z-index: 2;
  color: var(--accent);
  font-weight: 700;
}
.method-number {
  width: 30px;
  height: 30px;
  margin: 0 auto 9px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--accent-soft);
  color: var(--accent-deep);
  font-family: var(--font-heading);
}
.method-stage h3 { font-size: 12px; margin-bottom: 7px; }
.method-stage p { font-size: 10px; line-height: 1.4; color: var(--text-secondary); }
.feedback-loop {
  margin: 16px auto 0;
  max-width: 760px;
  border: 1px dashed #d6a55b;
  border-radius: 999px;
  padding: 8px 16px;
  text-align: center;
  font-size: 11px;
  color: var(--accent-deep);
  background: var(--accent-soft);
}
.chart-layout { display: grid; grid-template-columns: minmax(0, 2.2fr) minmax(240px, 1fr); gap: 24px; }
.ragas-chart {
  height: 310px;
  display: grid;
  grid-template-columns: 36px 1fr;
  grid-template-rows: 1fr 38px;
}
.chart-y-axis {
  grid-row: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  padding-right: 7px;
}
.chart-plot {
  grid-column: 2;
  grid-row: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  align-items: end;
  border-left: 1px solid var(--text-muted);
  border-bottom: 1px solid var(--text-muted);
  background: repeating-linear-gradient(to top, transparent 0, transparent calc(25% - 1px), var(--border) 25%);
  padding: 0 12px;
}
.chart-group { height: 100%; display: flex; gap: 5px; align-items: end; justify-content: center; }
.chart-bar { position: relative; width: 25%; min-width: 16px; border-radius: 4px 4px 0 0; }
.chart-bar.baseline { background: #a8a29e; }
.chart-bar.smart { background: var(--accent); }
.chart-bar.enhanced { background: #6b8a7a; }
.chart-bar span {
  position: absolute;
  top: -17px;
  left: 50%;
  transform: translateX(-50%);
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--text-secondary);
}
.chart-labels {
  grid-column: 2;
  grid-row: 2;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  text-align: center;
  padding: 7px 12px 0;
  font-size: 10px;
  color: var(--text-secondary);
}
.chart-legend { display: flex; gap: 14px; margin-bottom: 16px; flex-wrap: wrap; }
.legend-item { font-size: 11px; color: var(--text-secondary); }
.legend-swatch { width: 9px; height: 9px; border-radius: 2px; display: inline-block; margin-right: 5px; }
.finding-callout {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-sm);
  padding: 14px;
  margin-bottom: 10px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-secondary);
}
.finding-callout strong { color: var(--text); }
```

- [ ] **Step 2: Extend the responsive rules**

Inside the existing `@media (max-width: 768px)` block, add:

```css
.scope-grid,
.evidence-grid,
.gap-grid,
.chart-layout { grid-template-columns: 1fr; }
.methodology-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.method-stage:not(:last-child)::after { display: none; }
.evidence-card { min-height: auto; }
```

- [ ] **Step 3: Run the presentation contract**

Run:

```powershell
pytest tests/test_presentation_report.py -v --tb=short
```

Expected: the same content-contract failures remain; no new Python test errors are introduced.

- [ ] **Step 4: Commit the reusable styling layer**

```powershell
git add presentation/index.html
git commit -m "style: add academic research slide components"
```

### Task 3: Replace Slides 2–7 With the Research Narrative

**Files:**
- Modify: `presentation/index.html` slides 2–7.
- Test: `tests/test_presentation_report.py`

- [ ] **Step 1: Replace slide 2 with the strengthened problem statement**

Use the existing three-card component, change the heading to `Problem Statement`, and use these exact cards:

```html
<div class="problem-grid">
  <div class="problem-card"><div class="problem-num">1</div><h3>Information overload</h3><p>Lecture content is distributed across long PDF files, making the right explanation difficult to locate when students need it.</p></div>
  <div class="problem-card"><div class="problem-num">2</div><h3>Slow manual searching</h3><p>Keyword search and page-by-page reading consume revision time and can miss conceptually related passages.</p></div>
  <div class="problem-card"><div class="problem-num">3</div><h3>Ungrounded AI answers</h3><p>Generic assistants may answer beyond approved course material without showing the lecture source behind the response.</p></div>
</div>
<p class="prompt-note"><strong>Need:</strong> fast, source-grounded answers drawn from the student's own lecture notes.</p>
```

- [ ] **Step 2: Replace slide 3 with four measurable objectives**

Use the existing objective-item markup and these exact titles and descriptions:

```html
<div class="objectives-list">
  <div class="objective-item"><div class="objective-num">01</div><div><h3>Preserve lecture evidence</h3><p>Ingest PDF lecture notes while retaining source and page metadata for traceability.</p></div></div>
  <div class="objective-item"><div class="objective-num">02</div><div><h3>Retrieve relevant passages</h3><p>Combine dense semantic search with BM25 keyword matching to improve evidence discovery.</p></div></div>
  <div class="objective-item"><div class="objective-num">03</div><div><h3>Generate grounded answers</h3><p>Use retrieved context to produce answers with citations and transparent source snippets.</p></div></div>
  <div class="objective-item"><div class="objective-num">04</div><div><h3>Evaluate the complete system</h3><p>Assess retrieval, RAGAS answer quality, functionality, and practical response performance.</p></div></div>
</div>
```

- [ ] **Step 3: Replace slide 4 with scope and boundaries**

Use heading `Project Scope and Boundaries`, subtitle `A focused lecture-note assistant—not a general learning-management platform`, and:

```html
<div class="scope-grid">
  <article class="scope-card in-scope"><h3>In scope</h3><ul class="scope-list"><li>Text-readable PDF upload and extraction</li><li>Sentence-aware chunking with metadata</li><li>MiniLM embeddings and FAISS indexing</li><li>BM25 + dense hybrid retrieval with RRF</li><li>Gemini, OpenRouter, and local LLM generation</li><li>Cited answers, source snippets, web UI, and RAGAS evaluation</li></ul></article>
  <article class="scope-card out-scope"><h3>Out of scope</h3><ul class="scope-list"><li>Non-PDF learning sources and scanned-PDF OCR</li><li>Automatic marking or student grading</li><li>Course-authoring and content-management tools</li><li>Institution-wide LMS integration</li><li>Claims of universal subject expertise</li><li>Replacement of lecturers or human academic support</li></ul></article>
</div>
```

- [ ] **Step 4: Replace slide 5 with the verified top-three literature review**

Use heading `Literature Review — Top Three Studies` and create three `article.evidence-card` elements with `data-study-rank="1"`, `"2"`, and `"3"`. Their visible content must be:

```html
<div class="evidence-grid">
  <article class="evidence-card" data-study-rank="1"><div class="evidence-rank">Rank 01 · Educational QA</div><h3>Alawwad et al. (2025)</h3><p class="evidence-line"><strong>Method:</strong> Fine-tuned Llama-2 with semantic retrieval for textual textbook QA.</p><p class="evidence-line"><strong>Finding:</strong> 84.24% test accuracy on textual TQA.</p><p class="evidence-line"><strong>Limitation:</strong> Text only; diagrams and visual evidence are excluded.</p><p class="evidence-line"><strong>Project relevance:</strong> Closest evidence for RAG over structured lesson content.</p><p class="citation-line">Pattern Recognition · doi:10.1016/j.patcog.2024.111332</p></article>
  <article class="evidence-card" data-study-rank="2"><div class="evidence-rank">Rank 02 · Hybrid retrieval</div><h3>Hu et al. (2025)</h3><p class="evidence-line"><strong>Method:</strong> Multimodal parsing with sparse-dense hybrid retrieval and LLM generation.</p><p class="evidence-line"><strong>Finding:</strong> Reported correctness improved by 20.1% under the study setup.</p><p class="evidence-line"><strong>Limitation:</strong> Real-time retrieval at document scale still needs optimization.</p><p class="evidence-line"><strong>Project relevance:</strong> Supports combining BM25 and dense retrieval.</p><p class="citation-line">IEEE Access · doi:10.1109/ACCESS.2025.3544408</p></article>
  <article class="evidence-card" data-study-rank="3"><div class="evidence-rank">Rank 03 · Higher education</div><h3>Neumann et al. (2024)</h3><p class="evidence-line"><strong>Method:</strong> GPT-4 RAG chatbot in Moodle using LangChain and Weaviate.</p><p class="evidence-line"><strong>Finding:</strong> 88% response accuracy with positive student acceptance.</p><p class="evidence-line"><strong>Limitation:</strong> Human tutors remained preferred; automated fact-checking was weak.</p><p class="evidence-line"><strong>Project relevance:</strong> Demonstrates RAG as complementary academic support.</p><p class="citation-line">IEEE Transactions on Education · doi:10.1109/TE.2024.3467912</p></article>
</div>
```

- [ ] **Step 5: Replace slide 6 with the research gap and contribution**

Use two equal cards. The gap card states `Existing studies show useful RAG retrieval and generation, but practical lecture-note assistants still need transparent source traceability, hybrid retrieval, deployment choice, and integrated evaluation.` The contribution card states `This project combines PDF metadata, BM25 + FAISS retrieval, configurable cloud or local LLMs, cited answers, and RAGAS evaluation in one usable workflow.` Add a small footer: `Contribution is framed as an implementation response—not a claim of universal research novelty.`

- [ ] **Step 6: Replace slide 7 with the six-stage methodology flowchart**

Use heading `Methodology`, subtitle `Adapted CRISP-DM for iterative RAG system development`, and six `.method-stage` elements in this order:

```html
<div class="methodology-flow">
  <article class="method-stage"><div class="method-number">1</div><h3>Project and Problem Understanding</h3><p>Define the educational need, objectives, users, scope, and success criteria.</p></article>
  <article class="method-stage"><div class="method-number">2</div><h3>Lecture-Note Data Understanding</h3><p>Review PDF structure, text quality, page content, and traceability metadata.</p></article>
  <article class="method-stage"><div class="method-number">3</div><h3>PDF Extraction and Text Preparation</h3><p>Extract text and create 500-character chunks with 100-character overlap.</p></article>
  <article class="method-stage"><div class="method-number">4</div><h3>RAG Modelling and Application Development</h3><p>Embed, index, retrieve, fuse evidence, and generate cited answers.</p></article>
  <article class="method-stage"><div class="method-number">5</div><h3>Technical and Functional Evaluation</h3><p>Evaluate retrieval, RAGAS quality, software behaviour, and end-to-end use.</p></article>
  <article class="method-stage"><div class="method-number">6</div><h3>Deployment and Iterative Refinement</h3><p>Deploy, monitor, and use evidence and feedback to improve earlier stages.</p></article>
</div>
<div class="feedback-loop">↶ Evaluation and deployment findings feed back into data preparation and RAG modelling.</div>
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
pytest tests/test_presentation_report.py::test_research_slides_include_required_scope_and_methodology tests/test_presentation_report.py::test_literature_slide_uses_verified_top_three_studies -v
```

Expected: both tests pass. The 18-slide sequence test still fails until the remaining headings are updated.

- [ ] **Step 8: Commit the approved research narrative**

```powershell
git add presentation/index.html
git commit -m "feat: add scope literature and methodology slides"
```

### Task 4: Consolidate Slides 8–13 Around the Implemented System

**Files:**
- Modify: `presentation/index.html` slides 8–13.
- Test: `tests/test_presentation_report.py`

- [ ] **Step 1: Build slide 8 as architecture plus technology stack**

Use heading `System Architecture and Technology Stack`. Retain the three-tier architecture but update the retrieval service label to `FAISS · BM25 · Reciprocal Rank Fusion` and add one compact technology row below it containing `Vue 3 + Vite`, `Django 5.2`, `Sentence Transformers`, `FAISS + rank-bm25`, and `Gemini / OpenRouter / llama.cpp`. Do not list TailwindCSS as implemented unless it is confirmed in current frontend configuration.

- [ ] **Step 2: Build slide 9 as PDF ingestion and indexing**

Use heading `PDF Ingestion and Indexing` and a horizontal flow with the exact labels `Validate PDF`, `Extract page text`, `Create 500 / 100 chunks`, `Generate 384-d embeddings`, `Persist FAISS index`, and `Refresh hybrid index`. Add the note `Source filename and page metadata are retained for citations.`

- [ ] **Step 3: Build slide 10 as retrieval and answer generation**

Use heading `Retrieval and Answer-Generation Flow`. Show `User question → BM25 top 20 + FAISS top 20 → RRF fusion (k = 60) → optional cross-encoder reranking → final top 5 contexts → configured LLM → answer + source snippets`. Mark the reranker as optional because `data/rag_config.json` currently sets `reranker_enabled` to false.

- [ ] **Step 4: Build slide 11 as core technical design**

Use heading `Core Technical Design`. Present four compact cards:

```html
<div class="metrics-grid">
  <article class="metric-card"><div class="metric-name">Text preparation</div><div class="metric-value">500 / 100</div><div class="metric-desc">Current PDF indexing path: chunk size / overlap</div></article>
  <article class="metric-card"><div class="metric-name">Embedding</div><div class="metric-value">384-d</div><div class="metric-desc">all-MiniLM-L6-v2 sentence vectors</div></article>
  <article class="metric-card"><div class="metric-name">Candidate retrieval</div><div class="metric-value">20 + 20</div><div class="metric-desc">BM25 and dense candidates before fusion</div></article>
  <article class="metric-card"><div class="metric-name">Generation context</div><div class="metric-value">Top 5</div><div class="metric-desc">Fused evidence supplied to the configured LLM</div></article>
</div>
```

- [ ] **Step 5: Build slide 12 as interface and user workflow**

Use heading `Interface and User Workflow`. Retain `screenshots/01-main-ui.png`, remove the standalone Vue promotional row, and add a four-step caption below the screenshot: `1 Upload lecture notes · 2 Select sources · 3 Ask a question · 4 Inspect citations and snippets`.

- [ ] **Step 6: Rename and retain slide 13 as the chat demonstration**

Use heading `Chat Demonstration`. Retain the existing application screenshot and example conversation, but change the source box to `Answer evidence: lecture3.pdf · p.12 and lecture5.pdf · p.8` and ensure the demo is clearly labelled `Illustrative interaction` rather than measured output.

- [ ] **Step 7: Run the sequence test**

Run:

```powershell
pytest tests/test_presentation_report.py::test_presentation_contains_approved_18_slide_sequence -v
```

Expected: failure now points only to slides 14–16 headings.

- [ ] **Step 8: Commit the consolidated system narrative**

```powershell
git add presentation/index.html
git commit -m "refactor: consolidate presentation system flow"
```

### Task 5: Replace Slides 14–16 With Evaluation Method, Graph, and Findings

**Files:**
- Modify: `presentation/index.html` slides 14–16.
- Test: `tests/test_presentation_report.py`

- [ ] **Step 1: Rewrite slide 14 as evaluation method**

Use heading `Evaluation Method — RAGAS`, subtitle `Four complementary dimensions scored on the same 25 question/reference pairs`, and retain four metric cards with definitions only. Remove the fabricated per-metric values from this slide. Use these definitions:

- Faithfulness — `Are answer claims supported by retrieved context?`
- Answer relevancy — `Does the response directly address the question?`
- Context precision — `How much retrieved evidence is relevant?`
- Context recall — `How much required evidence was retrieved?`

Add the note `Scores range from 0 to 1; higher is better. Values are summarized on the next slide.`

- [ ] **Step 2: Replace slide 15 with the grouped RAGAS bar chart**

Use heading `RAGAS Results`. Add the exact machine-readable series attributes:

```html
<div class="chart-series-data" hidden>
  <span data-series="baseline" data-values="0.85,0.86,0.67,0.84"></span>
  <span data-series="smart-chunking" data-values="0.59,0.60,0.29,0.24"></span>
  <span data-series="enhanced-retrieval" data-values="0.65,0.80,0.53,0.58"></span>
</div>
```

Build four `.chart-group` elements. Each contains baseline, smart, and enhanced bars with heights equal to the percentage score and labels equal to the two-decimal score. For Faithfulness, for example:

```html
<div class="chart-group">
  <div class="chart-bar baseline" style="height:85%"><span>0.85</span></div>
  <div class="chart-bar smart" style="height:59%"><span>0.59</span></div>
  <div class="chart-bar enhanced" style="height:65%"><span>0.65</span></div>
</div>
```

Repeat with `86/60/80`, `67/29/53`, and `84/24/58`. The four x-axis labels are `Faithfulness`, `Answer relevancy`, `Context precision`, and `Context recall`. Use a zero-to-one y-axis with labels `1.0`, `0.75`, `0.50`, `0.25`, and `0.0`. The legend maps grey to Original baseline, amber to Smart chunking, and sage to Enhanced retrieval.

Add a side panel containing:

```html
<div class="finding-callout"><strong>Recovered after retrieval changes:</strong> enhanced retrieval exceeded the smart-chunking run on all four metrics.</div>
<div class="finding-callout"><strong>Baseline still strongest:</strong> the original run remained highest overall, so later changes are not presented as a universal improvement.</div>
<p class="eval-note">Means recalculated from 25 identical question/reference pairs per run.</p>
```

- [ ] **Step 3: Replace slide 16 with findings and discussion**

Use heading `Findings and Discussion` and four cards:

1. `Grounding remains the priority` — faithfulness recovered from 0.59 to 0.65, but remained below the 0.85 baseline.
2. `Retrieval changes involve trade-offs` — context precision and recall improved over the smart-chunking run without surpassing the original evaluation.
3. `One change at a time` — future experiments should isolate chunking, retrieval, reranking, and prompting so effects can be attributed.
4. `Evaluation is iterative` — retain the best configuration only after repeated runs and human review of retrieved evidence.

- [ ] **Step 4: Run evaluation-specific tests**

Run:

```powershell
pytest tests/test_presentation_report.py::test_results_graph_embeds_recalculated_ragas_means tests/test_presentation_report.py::test_unsupported_legacy_claims_are_removed -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit the evidence-based evaluation section**

```powershell
git add presentation/index.html
git commit -m "feat: visualize verified ragas evaluation results"
```

### Task 6: Update Limitations, Conclusion, and Navigation Semantics

**Files:**
- Modify: `presentation/index.html` slides 17–18 and navigation markup.
- Test: `tests/test_presentation_report.py`

- [ ] **Step 1: Correct slide 17 limitations and future work**

Use heading `Limitations and Future Work`. Remove `Hybrid retrieval combining BM25 and dense vectors` from future work because hybrid retrieval is implemented. Use:

**Current limitations:** text-readable PDFs only; evaluation uses 25 question/reference pairs; answer quality depends on retrieved evidence and the configured LLM; local models require suitable hardware.

**Future work:** OCR and layout-aware parsing; broader multi-course evaluation with human review; tuned reranking and retrieval ablations; authentication and LMS integration.

- [ ] **Step 2: Update the conclusion to match the evidence**

Keep heading `Conclusion` and use three conclusion items:

1. `Built a complete lecture-note RAG workflow from PDF ingestion to cited answers.`
2. `Combined semantic and keyword retrieval with configurable cloud or local generation.`
3. `Used RAGAS evidence to identify both strengths and the next retrieval improvements.`

Retain `Thank You` and `Questions & Discussion`.

- [ ] **Step 3: Add slide accessibility semantics**

Give each section `aria-label="Slide N of 18: <heading>"`, set inactive sections to `aria-hidden="true"`, and update the existing `showSlide` function so it runs:

```javascript
slides.forEach(function (slide, index) {
  var isActive = index === current;
  slide.classList.toggle('active', isActive);
  slide.setAttribute('aria-hidden', String(!isActive));
});
```

Keep `var total = slides.length;` and `totalEl.textContent = total;` as the source of truth.

- [ ] **Step 4: Run the complete presentation test file**

Run:

```powershell
pytest tests/test_presentation_report.py -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 5: Run formatting checks on changed files**

Run:

```powershell
git diff --check -- presentation/index.html tests/test_presentation_report.py
ruff check tests/test_presentation_report.py
black --check tests/test_presentation_report.py
```

Expected: no whitespace errors; Ruff and Black both pass.

- [ ] **Step 6: Commit the final content and semantics**

```powershell
git add presentation/index.html tests/test_presentation_report.py
git commit -m "fix: align presentation claims and navigation semantics"
```

### Task 7: Browser Verification and Visual Repair

**Files:**
- Inspect: `presentation/index.html`
- Modify if required: `presentation/index.html`
- Test: `tests/test_presentation_report.py`

- [ ] **Step 1: Serve the repository locally**

Run from the repository root:

```powershell
python -m http.server 8765
```

Expected: the presentation is available at `http://localhost:8765/presentation/index.html`.

- [ ] **Step 2: Verify the browser console and initial render**

Open the presentation with the in-app browser. Confirm the title slide, hero image, Google Fonts fallback behavior, progress bar, counter `1 / 18`, and absence of console errors.

- [ ] **Step 3: Exercise navigation**

Verify:

- right arrow advances exactly one slide;
- left arrow returns exactly one slide;
- Space advances and Shift+Space returns;
- clicking the right and left margins navigates;
- a horizontal swipe changes slides once;
- the final slide displays `18 / 18`; and
- navigation clamps at the first and final slides.

- [ ] **Step 4: Inspect all slides at 1366 × 768**

Capture or inspect each of the 18 slides. Check for clipped text, overlapping arrows, overflowing literature cards, unreadable chart values, hidden citation lines, and excessive density. Pay particular attention to slides 5, 7, 10, and 15.

- [ ] **Step 5: Inspect all slides at 1920 × 1080**

Repeat the visual pass at full HD. Confirm slide content remains centered and does not expand into unreadably long lines.

- [ ] **Step 6: Repair any visual defects and rerun checks**

If a slide clips, first reduce internal gaps or copy length; do not reduce body text below 11px or hide evidence. After any repair, run:

```powershell
pytest tests/test_presentation_report.py -v --tb=short
git diff --check -- presentation/index.html tests/test_presentation_report.py
```

Expected: all tests pass and no whitespace errors remain.

- [ ] **Step 7: Commit visual repairs if any**

```powershell
git add presentation/index.html tests/test_presentation_report.py
git commit -m "fix: polish presentation layout at defense viewports"
```

### Task 8: Final Verification

**Files:**
- Verify: `presentation/index.html`
- Verify: `tests/test_presentation_report.py`

- [ ] **Step 1: Run the focused presentation suite**

```powershell
pytest tests/test_presentation_report.py -v --tb=short
```

Expected: all presentation tests pass.

- [ ] **Step 2: Run relevant repository quality checks**

```powershell
ruff check tests/test_presentation_report.py
black --check tests/test_presentation_report.py
git diff --check -- presentation/index.html tests/test_presentation_report.py
```

Expected: every command exits successfully.

- [ ] **Step 3: Audit the final diff**

Run:

```powershell
git diff --stat HEAD~1
git status --short
```

Confirm that presentation work touches only `presentation/index.html` and `tests/test_presentation_report.py`, apart from the approved specification and this plan. Do not stage or alter unrelated working-tree files.

- [ ] **Step 4: Confirm acceptance criteria**

Check all of the following manually:

- exactly 18 slides;
- 15-minute narrative order;
- replaced, non-duplicated problem and objective slides;
- explicit scope boundaries;
- exactly three source-verified literature studies;
- research-gap synthesis;
- six-stage methodology flowchart with feedback loop;
- grouped graph with actual RAGAS means and cautious interpretation;
- unsupported benchmark claims removed;
- hybrid retrieval described as implemented, not future work;
- working keyboard, click, and touch navigation; and
- no clipping or console errors at both target viewports.
