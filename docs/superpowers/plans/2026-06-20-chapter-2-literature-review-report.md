# Chapter 2 Literature Review Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a comprehensive, source-verified Chapter 2 literature review and project-planning report as matching DOCX and PDF files.

**Architecture:** Build a structured evidence record from the ranked workbook and corresponding journal PDFs, synthesize that evidence against the current repository implementation, then generate an academic DOCX with deterministic styles, tables, references, and a Gantt chart. Render the DOCX to page images and PDF, inspect every page, repair defects, and deliver only the final artifacts.

**Tech Stack:** `@oai/artifact-tool` for workbook inspection, bundled Python with `pypdf` and `python-docx`, the packaged DOCX renderer/LibreOffice, and PDFium/Pillow for PDF verification.

---

### Task 1: Build the literature evidence record

**Files:**
- Read: `fyp/03-literature/literature_review_ranked_by_relevance.xlsx`
- Read: `fyp/03-literature/journal/*.pdf`
- Create: `tmp/report_build/literature_evidence.json`

- [ ] **Step 1: Read the ranking workbook**

Import the workbook with `@oai/artifact-tool` and inspect `Ranking Summary!A1:E17` and `Ranked Literature!A1:M30`. Preserve rank, original paper number, title, authors, year, methods, reported result, advantages, limitations, and relevance.

- [ ] **Step 2: Match the highest-ranked studies to PDFs**

Match normalized titles for ranks 1-15 against filenames in `fyp/03-literature/journal/`. Record the exact PDF path and flag any missing or ambiguous match.

- [ ] **Step 3: Extract auditable evidence**

Use bundled `pypdf` to extract each selected PDF's metadata and text. Capture title, authors, publication year, DOI or stable publication identifier when present, abstract, method snippet, result snippet, limitation/conclusion snippet, and page references.

- [ ] **Step 4: Verify spreadsheet claims**

For each selected study, mark every workbook claim as `verified`, `qualified`, or `not_located`. Use only verified or clearly qualified claims in the report.

- [ ] **Step 5: Validate the evidence file**

Run:

```powershell
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m json.tool tmp\report_build\literature_evidence.json
```

Expected: valid JSON with no parsing error and at least ten fully matched high-relevance studies.

### Task 2: Confirm the implemented project profile

**Files:**
- Read: `requirements.txt`
- Read: `app/config.py`
- Read: `app/services/local_rag.py`
- Read: `app/services/pdf_indexing.py`
- Read: `app/services/hybrid_retriever_service.py`
- Read: `app/services/cross_encoder_reranker.py`
- Read: `retrieval/hybrid_retriever.py`
- Read: `evaluation/ragas_evaluator.py`
- Read: `django_app/views/rag.py`
- Read: `frontend/src/README.md`
- Read: `PROJECT_PROPOSAL.md`
- Create: `tmp/report_build/project_evidence.json`

- [ ] **Step 1: Record implemented techniques**

Confirm document parsing, chunking, sentence embeddings, FAISS indexing, BM25, hybrid fusion, optional cross-encoder reranking, multi-provider generation, citation/source output, Vue frontend, and RAGAS evaluation from current source files.

- [ ] **Step 2: Separate status levels**

Classify each capability as `implemented`, `optional/configurable`, `evaluation-only`, or `planned`. Do not treat proposal-only statements as implementation evidence.

- [ ] **Step 3: Record project requirements**

Extract required Python packages, optional services, model/API dependencies, storage paths, supported providers, and practical local-inference requirements.

- [ ] **Step 4: Record the approved schedule**

Capture the seven phases and 16-week timeline from `PROJECT_PROPOSAL.md`.

### Task 3: Draft the academic chapter

**Files:**
- Read: `docs/superpowers/specs/2026-06-20-chapter-2-literature-review-report-design.md`
- Read: `tmp/report_build/literature_evidence.json`
- Read: `tmp/report_build/project_evidence.json`
- Create: `tmp/report_build/chapter2_content.json`

- [ ] **Step 1: Draft Section 2.1**

Write an introduction that defines the chapter's purpose, scope, thematic organization, and relationship to the project without describing methodology.

- [ ] **Step 2: Draft Section 2.2.1**

Synthesize the educational technology, NLP, information retrieval, document QA, LLM, and RAG domains with source-supported definitions and project relevance.

- [ ] **Step 3: Draft Section 2.2.2**

Write a critical thematic synthesis of the highest-ranked systems. Include a structured comparison dataset for a table with columns for system, domain/input, retrieval and generation approach, reported result, limitation, and project relevance.

- [ ] **Step 4: Draft Section 2.2.3**

Review extraction, chunking, embeddings, dense retrieval, BM25, hybrid fusion, FAISS/indexing, reranking, generation, citation grounding, and RAGAS evaluation. Include an alternatives dataset and explicit reasons for non-adoption.

- [ ] **Step 5: Draft Sections 2.4-2.6**

Write software, hardware, and other requirements; the 16-week schedule and milestone descriptions; and a concluding synthesis. Retain the rubric's section numbering and omit Section 2.3 completely.

- [ ] **Step 6: Build the APA 7 reference list**

Create one reference entry per cited work. Ensure every citation key used in prose resolves to exactly one reference entry.

- [ ] **Step 7: Run content checks**

Check for unsupported numbers, methodology leakage, duplicated paper #24, missing citation keys, uncited references, placeholders, and claims that confuse incomparable datasets.

### Task 4: Generate the DOCX and PDF

**Files:**
- Create: `tmp/report_build/generate_chapter2_report.py`
- Create: `output/reports/chapter_2_literature_review_and_project_planning.docx`
- Create: `output/reports/chapter_2_literature_review_and_project_planning.pdf`

- [ ] **Step 1: Configure document geometry and styles**

Use A4 portrait, conventional academic margins, Times New Roman 12 pt body text, justified paragraphs, 1.5 line spacing, consistent numbered headings, and a restrained running header/footer with page numbers.

- [ ] **Step 2: Compose the document**

Generate the chapter title, numbered sections, comparison tables, requirements lists, one-page Gantt chart, summary, and APA references from `chapter2_content.json`. Keep table headers repeating and rows flexible.

- [ ] **Step 3: Export the DOCX**

Run the bundled Python generator and confirm the DOCX exists and opens structurally with `python-docx`.

- [ ] **Step 4: Render to PDF and PNG**

Run:

```powershell
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'C:\Users\wongs\.codex\plugins\cache\openai-primary-runtime\documents\26.614.11602\skills\documents\render_docx.py' output\reports\chapter_2_literature_review_and_project_planning.docx --output_dir tmp\report_render --emit_pdf
```

Expected: one PDF and one PNG per page.

### Task 5: Verify and repair the final artifacts

**Files:**
- Inspect: `tmp/report_render/page-*.png`
- Inspect: `output/reports/chapter_2_literature_review_and_project_planning.docx`
- Inspect: `output/reports/chapter_2_literature_review_and_project_planning.pdf`

- [ ] **Step 1: Inspect every rendered page**

Check text clipping, table width, row splitting, heading orphans, large blank areas, font substitution, page numbering, header consistency, Gantt readability, and reference formatting.

- [ ] **Step 2: Repair meaningful defects**

Patch the generator or content source, regenerate both outputs, and rerender after any layout-sensitive change.

- [ ] **Step 3: Run structural checks**

Confirm page count, heading sequence, presence of Sections 2.1, 2.2.1-2.2.3, 2.4.1-2.4.3, 2.5, and 2.6, absence of Section 2.3, citation-reference parity, and lack of `TBD`, `TODO`, or internal citation tokens.

- [ ] **Step 4: Deliver final files**

Provide direct links to the verified DOCX and PDF and briefly summarize the source basis and methodology omission.
