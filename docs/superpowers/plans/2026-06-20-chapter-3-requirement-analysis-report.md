# Chapter 3 Requirement Analysis Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an evidence-based, formally formatted Chapter 3 Requirement Analysis report as matching DOCX and PDF files.

**Architecture:** Extract current requirements from repository code and tests into one structured JSON content model, generate three consistent academic diagrams, and assemble the narrative, requirement matrices, data dictionary, and visuals with `python-docx`. Render the DOCX through LibreOffice, inspect every page as PNG, validate content mechanically, and publish only the verified DOCX and PDF.

**Tech Stack:** Python 3, `python-docx`, Pillow or Matplotlib, repository source files, LibreOffice headless, PDFium, and packaged document-rendering scripts.

---

## File Structure

- Create `tmp/report_build/build_chapter3_content.py`: collect verified repository evidence and write the complete report content model.
- Create `tmp/report_build/chapter3_content.json`: generated narrative, requirement records, data dictionary, and requirement tables.
- Create `tmp/report_build/generate_chapter3_diagrams.py`: generate the manual-search, proposed-RAG, and use-case diagrams from fixed semantic definitions.
- Create `tmp/report_build/chapter3_diagrams/*.png`: high-resolution intermediate diagram assets.
- Create `tmp/report_build/generate_chapter3_report.py`: assemble and style the DOCX.
- Create `tmp/report_build/validate_chapter3_report.py`: verify required headings, IDs, captions, unsupported-claim markers, and output integrity.
- Create `output/reports/chapter_3_requirement_analysis.docx`: final editable report.
- Create `output/reports/chapter_3_requirement_analysis.pdf`: final matching PDF.
- Create `tmp/report_build/chapter3_render/`: temporary page PNGs used for visual verification.

### Task 1: Build the verified evidence inventory

**Files:**
- Read: `app/config.py`
- Read: `app/services/pdf_indexing.py`
- Read: `app/services/pdf_chunking.py`
- Read: `app/services/embedding.py`
- Read: `app/services/vector_store.py`
- Read: `app/services/hybrid_retriever_service.py`
- Read: `app/services/local_rag.py`
- Read: `app/services/conversation_service.py`
- Read: `django_app/models.py`
- Read: `django_app/views/documents.py`
- Read: `django_app/views/rag.py`
- Read: `django_app/views/conversations.py`
- Read: `django_backend/urls.py`
- Read: `tests/test_django_upload.py`
- Read: `tests/test_django_ask_view.py`
- Read: `tests/test_conversation_service.py`
- Create: `tmp/report_build/build_chapter3_content.py`

- [ ] **Step 1: Record implemented interfaces and configuration values**

Create explicit constants in `build_chapter3_content.py` for verified values such as:

```python
VERIFIED_PARAMETERS = {
    "chunk_size": 500,
    "chunk_overlap": 100,
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_dimension": 384,
    "maximum_upload_bytes": 10 * 1024 * 1024,
    "local_llm_timeout_seconds": 300,
    "upload_indexing_strategy": "full_rebuild",
    "upload_indexing_async": True,
}
```

Cross-check every value directly against `app/config.py`; if runtime configuration can override it, describe it as a default rather than an invariant.

- [ ] **Step 2: Record implementation-status labels**

Use only these status values throughout the content model:

```python
IMPLEMENTED = "Implemented"
CONFIGURABLE = "Implemented and configurable"
OPTIONAL = "Optional deployment dependency"
EXPERIMENTAL = "Experimental or evaluation-oriented"
TARGET = "Target for later verification"
```

- [ ] **Step 3: Verify evidence coverage**

Run:

```powershell
rg -n "CHUNK_SIZE|CHUNK_OVERLAP|MAX_UPLOAD_SIZE|LOCAL_LLM_TIMEOUT_SECONDS|class Conversation|class Message|def upload_pdf|def ask\(" app django_app
```

Expected: matches in configuration, models, upload view, and Q&A view that support every core parameter and stored entity used by the report.

### Task 2: Write the complete Chapter 3 content model

**Files:**
- Modify: `tmp/report_build/build_chapter3_content.py`
- Create: `tmp/report_build/chapter3_content.json`

- [ ] **Step 1: Define the chapter narrative**

Write formal, project-specific paragraphs for `3.1 Introduction`, `3.2 Problem Analysis`, `3.3 Requirement Analysis`, its four subsections, and `3.4 Summary`. The content object must use this stable shape:

```python
content = {
    "title": "CHAPTER 3",
    "subtitle": "REQUIREMENT ANALYSIS",
    "sections": [
        {"heading": "3.1 Introduction", "paragraphs": ["This chapter translates the identified educational problem into verifiable system requirements for the lecture-note question-answering application."]},
        {"heading": "3.2 Problem Analysis", "paragraphs": ["Students currently locate evidence by opening lecture files, searching keywords, scanning candidate pages, and manually combining relevant passages."]},
        {"heading": "3.3 Requirement Analysis", "paragraphs": ["The analysis defines the data, functional, quality, operational, software, and hardware conditions needed for the system."]},
        {"heading": "3.3.1 Data Requirement", "paragraphs": ["The system accepts text-readable PDF lecture notes and user questions, then produces indexed chunks, retrieved evidence, grounded answers, and source metadata."]},
        {"heading": "3.3.2 Functional Requirement", "paragraphs": ["Functional requirements specify observable behaviours from document upload through retrieval, answer generation, source inspection, and administration."]},
        {"heading": "3.3.3 Non-functional Requirement", "paragraphs": ["Non-functional requirements establish measurable expectations for usability, performance, reliability, security, maintainability, compatibility, and accessibility."]},
        {"heading": "3.3.4 Other Requirement", "paragraphs": ["Operation requires a supported Python and web-development environment, sufficient compute and storage, readable lecture documents, and authorised model access where applicable."]},
        {"heading": "3.4 Summary", "paragraphs": ["The resulting requirements provide the baseline for detailed design, implementation, integration, and systematic evaluation in subsequent work."]},
    ],
}
```

- [ ] **Step 2: Define the data dictionary**

Add records with the exact keys `element`, `format`, `source`, `purpose`, `storage`, and `validation`. Include PDF files, page-aware text chunks, embeddings, FAISS vectors and metadata, user queries, retrieved evidence, generated answers, conversations, messages, configuration, query logs, system metrics, and summaries.

- [ ] **Step 3: Define functional requirements**

Create stable IDs `FR-01` through at least `FR-14`. Each record must contain `id`, `requirement`, `actor`, `input`, `processing`, `output`, `acceptance`, and `status`. Cover upload validation, parsing, chunking, indexing, document management, question submission, retrieval, answer generation, source transparency, conversation history, summaries, suggestions, runtime configuration, and monitoring.

- [ ] **Step 4: Define non-functional requirements**

Create stable IDs `NFR-01` through at least `NFR-12`. Each record must contain `id`, `category`, `requirement`, `measure`, `verification`, and `status`. Treat unmeasured latency, retrieval quality, availability, and accessibility values as targets rather than achieved results.

- [ ] **Step 5: Define software and hardware requirements**

Create software records with `component`, `role`, `justification`, and `status`, and hardware records with `component`, `cloud_minimum`, `recommended_development`, `local_inference`, and `justification`.

- [ ] **Step 6: Generate the JSON content model**

Implement:

```python
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(
    json.dumps(content, indent=2, ensure_ascii=True),
    encoding="utf-8",
)
```

Run:

```powershell
python tmp/report_build/build_chapter3_content.py
```

Expected: `tmp/report_build/chapter3_content.json` exists and contains all eight numbered headings, contiguous functional and non-functional requirement IDs, and no empty values.

### Task 3: Generate the academic diagrams

**Files:**
- Create: `tmp/report_build/generate_chapter3_diagrams.py`
- Create: `tmp/report_build/chapter3_diagrams/manual_search_activity.png`
- Create: `tmp/report_build/chapter3_diagrams/proposed_rag_workflow.png`
- Create: `tmp/report_build/chapter3_diagrams/system_use_cases.png`

- [ ] **Step 1: Implement shared diagram styling**

Use A4-compatible proportions, 300 DPI, Times New Roman labels, dark navy headings, pale blue process boxes, white background, and grey connectors. Define shared drawing helpers:

```python
def draw_box(ax, x, y, width, height, title, body="") -> None:
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.02",
        facecolor="#EAF2F8",
        edgecolor="#234E70",
        linewidth=1.5,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height * 0.68, title, ha="center", va="center", weight="bold")
    if body:
        ax.text(x + width / 2, y + height * 0.34, body, ha="center", va="center", wrap=True)


def draw_arrow(ax, start, end, label="") -> None:
    ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": "#666666", "lw": 1.4})
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2, label, ha="center", va="bottom", fontsize=9)


def save_figure(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
```

- [ ] **Step 2: Draw the current manual-search activity**

Show the sequence: identify information need, open lecture PDFs, search keywords or scan pages, inspect candidate passages, decide whether evidence is sufficient, formulate an answer manually, and repeat when evidence is insufficient.

- [ ] **Step 3: Draw the proposed RAG workflow**

Show two connected flows: PDF upload to extraction, chunking, embedding, and FAISS/BM25 indexing; then question to query embedding, retrieval, context construction, LLM generation, and answer with sources.

- [ ] **Step 4: Draw the use-case diagram**

Place `Student / User` and `System Administrator / Maintainer` outside the system boundary. Connect the user to upload notes, manage source selection, ask questions, inspect sources, continue conversations, generate summaries, and view suggestions. Connect the maintainer to configure providers and retrieval, monitor health and metrics, manage documents, and run evaluation-oriented tools.

- [ ] **Step 5: Render and inspect diagram files**

Run:

```powershell
python tmp/report_build/generate_chapter3_diagrams.py
```

Expected: three PNG files, each at least 1800 pixels wide, with no clipped labels or crossing connectors.

### Task 4: Assemble the formal DOCX

**Files:**
- Create: `tmp/report_build/generate_chapter3_report.py`
- Read: `tmp/report_build/chapter3_content.json`
- Read: `tmp/report_build/chapter3_diagrams/*.png`
- Create: `output/reports/chapter_3_requirement_analysis.docx`

- [ ] **Step 1: Configure the academic style system**

Use A4 portrait, 2.54 cm top/bottom/right margins, 2.8 cm left margin, Times New Roman 12 pt, 1.5 line spacing, justified body paragraphs, 0.5-inch first-line indent, bold numbered headings, and caption text at 10 pt. Add a quiet running header and centered PAGE field.

- [ ] **Step 2: Implement reusable document helpers**

Implement helpers with these signatures:

```python
def set_run_font(run, size: float, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Times New Roman")


def add_body_paragraph(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.line_spacing = 1.5
    paragraph.paragraph_format.first_line_indent = Inches(0.5)
    paragraph.paragraph_format.space_after = Pt(6)
    set_run_font(paragraph.add_run(text), 12)


def add_heading(doc: Document, heading: str) -> None:
    level = 2 if heading.count(".") >= 2 else 1
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    paragraph.paragraph_format.keep_with_next = True
    set_run_font(paragraph.add_run(heading), 12 if level == 2 else 13, bold=True)


def add_figure(doc: Document, path: Path, caption: str, width_inches: float) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(str(path), width=Inches(width_inches))
    doc.add_paragraph(caption, style="Caption")


def add_table(doc: Document, caption: str, headers, rows, widths, font_size: float) -> None:
    doc.add_paragraph(caption, style="Caption")
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    for index, header in enumerate(headers):
        table.columns[index].width = Inches(widths[index])
        cell = table.rows[0].cells[index]
        cell.text = header
        set_run_font(cell.paragraphs[0].runs[0], font_size, bold=True)
    for values in rows:
        cells = table.add_row().cells
        for index, value in enumerate(values):
            cells[index].text = str(value)
            set_run_font(cells[index].paragraphs[0].runs[0], font_size)
```

Tables must repeat header rows, avoid fixed row heights, prevent row splitting where practical, use content-driven widths, and apply consistent cell padding.

- [ ] **Step 3: Add the chapter title and sections**

Insert the title block and all numbered sections in guideline order. Insert `Figure 3.1` after the current-scenario analysis, `Figure 3.2` after the proposed-system process, and `Figure 3.3` in the functional-requirement subsection.

- [ ] **Step 4: Add requirement tables**

Insert:

- `Table 3.1` Data Dictionary
- `Table 3.2` Functional Requirements
- `Table 3.3` Non-functional Requirements
- `Table 3.4` Software Requirements
- `Table 3.5` Hardware Requirements

Use landscape sections for Tables 3.1 to 3.3 if portrait layout would make the text unreadable, then restore portrait orientation before the next narrative section.

- [ ] **Step 5: Save clean document metadata**

Set the title and subject, leave the author blank, use keywords `RAG, lecture notes, requirement analysis, functional requirements`, and save to `output/reports/chapter_3_requirement_analysis.docx`.

- [ ] **Step 6: Generate the DOCX**

Run:

```powershell
python tmp/report_build/generate_chapter3_report.py
```

Expected: the DOCX exists, is non-empty, and opens without package errors.

### Task 5: Add deterministic content validation

**Files:**
- Create: `tmp/report_build/validate_chapter3_report.py`
- Read: `tmp/report_build/chapter3_content.json`
- Read: `output/reports/chapter_3_requirement_analysis.docx`

- [ ] **Step 1: Validate content-model invariants**

Implement checks for required headings, unique contiguous IDs, non-empty acceptance criteria, allowed status labels, ASCII-safe punctuation, and absence of unsupported completion language such as `achieved`, `proven`, or `meets target` when attached to target-only metrics.

- [ ] **Step 2: Validate DOCX structure**

Using `python-docx`, assert that all headings, figure captions, table captions, and requirement IDs occur in the document. Open the DOCX as a ZIP archive and assert that all three diagram assets are present under `word/media/`.

- [ ] **Step 3: Run validation**

Run:

```powershell
python tmp/report_build/validate_chapter3_report.py
```

Expected: exit code 0 with a summary reporting eight required headings, three figures, five tables, and complete requirement-ID coverage.

### Task 6: Render, inspect, and refine the final report

**Files:**
- Read: `output/reports/chapter_3_requirement_analysis.docx`
- Create: `tmp/report_build/chapter3_render/page-*.png`
- Create: `output/reports/chapter_3_requirement_analysis.pdf`

- [ ] **Step 1: Render DOCX to PNG and PDF**

Run the packaged renderer:

```powershell
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\wongs\.codex\plugins\cache\openai-primary-runtime\documents\26.614.11602\skills\documents\render_docx.py' `
  'output\reports\chapter_3_requirement_analysis.docx' `
  --output_dir 'tmp\report_build\chapter3_render' --emit_pdf
```

Expected: one PNG per report page and a non-empty PDF.

- [ ] **Step 2: Inspect every rendered page**

Check every page at full resolution for clipped text, overcrowded tables, split captions, orphaned headings, inconsistent margins, font substitution, missing diagrams, bad page orientation, and header/footer collisions.

- [ ] **Step 3: Correct all visual defects**

Adjust diagram scale, table widths, font size, cell padding, section breaks, or paragraph keep rules in `generate_chapter3_report.py`; regenerate, revalidate, and rerender after every meaningful correction.

- [ ] **Step 4: Publish the verified PDF**

Copy the renderer-produced PDF to `output/reports/chapter_3_requirement_analysis.pdf` and confirm the DOCX and PDF page counts match.

### Task 7: Final verification and handoff

**Files:**
- Read: `output/reports/chapter_3_requirement_analysis.docx`
- Read: `output/reports/chapter_3_requirement_analysis.pdf`

- [ ] **Step 1: Run the final mechanical checks**

Run:

```powershell
python tmp/report_build/validate_chapter3_report.py
Get-Item output/reports/chapter_3_requirement_analysis.docx,output/reports/chapter_3_requirement_analysis.pdf
```

Expected: validator exit code 0 and both files have non-zero sizes.

- [ ] **Step 2: Confirm delivery quality**

Verify that the latest render contains no visual defects, the report follows the supplied guideline, all targets are labelled honestly, and the output directory contains the stable final filenames.

- [ ] **Step 3: Report completion**

Provide clickable links to the final DOCX and PDF and summarize the included sections and verification performed.
