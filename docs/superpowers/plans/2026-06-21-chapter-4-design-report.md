# Chapter 4 Design Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an evidence-based Chapter 4 Design report as visually matching DOCX and PDF files.

**Architecture:** Build a verified evidence model from the current application, generate a coherent set of academic diagrams and interface evidence, and assemble the narrative, pseudocode, matrices, figures, and data model with `python-docx`. Validate structure mechanically, render every page through LibreOffice, inspect all page images, and publish only the final verified DOCX and PDF.

**Tech Stack:** Bundled Python 3, `python-docx`, Pillow, Matplotlib, Pydantic-aware source inspection, LibreOffice headless, Poppler, the in-app browser when the local UI is runnable, and packaged document-rendering scripts.

---

## File Structure

- Create `tmp/report_build/chapter4/build_chapter4_content.py`: encode verified repository evidence and the complete report content model.
- Create `tmp/report_build/chapter4/chapter4_content.json`: generated narrative, matrices, data dictionary, algorithm definitions, and captions.
- Create `tmp/report_build/chapter4/generate_chapter4_diagrams.py`: produce all architecture, workflow, navigation, ERD, AI, component, and sequence diagrams.
- Create `tmp/report_build/chapter4/diagrams/*.png`: high-resolution intermediate visual assets.
- Create `tmp/report_build/chapter4/ui/*.png`: current interface captures or implementation-grounded mock-ups.
- Create `tmp/report_build/chapter4/generate_chapter4_report.py`: assemble and style the DOCX.
- Create `tmp/report_build/chapter4/validate_chapter4_report.py`: check required structure, captions, evidence labels, embedded media, and output integrity.
- Create `output/reports/chapter_4_design.docx`: final editable report.
- Create `output/reports/chapter_4_design.pdf`: final matching PDF.
- Create `tmp/report_build/chapter4/render/`: temporary page PNGs and renderer output used for visual verification.

### Task 1: Build the verified design evidence inventory

**Files:**
- Read: `app/config.py`
- Read: `app/services/pdf_loader.py`
- Read: `app/services/pdf_indexing.py`
- Read: `app/services/pdf_chunking.py`
- Read: `app/services/embedding.py`
- Read: `app/services/vector_store.py`
- Read: `app/services/hybrid_retriever_service.py`
- Read: `app/services/cross_encoder_reranker.py`
- Read: `app/services/local_rag.py`
- Read: `app/services/citation_rag.py`
- Read: `app/services/summarizer.py`
- Read: `app/services/question_suggestions.py`
- Read: `django_app/models.py`
- Read: `django_app/views/documents.py`
- Read: `django_app/views/rag.py`
- Read: `django_app/views/ops.py`
- Read: `django_backend/urls.py`
- Read: `frontend/src/App.vue`
- Read: `frontend/src/components/`
- Read: `frontend/src/services/api.js`
- Read: `retrieval/bm25_index.py`
- Read: `retrieval/hybrid_retriever.py`
- Read: `evaluation/`
- Create: `tmp/report_build/chapter4/build_chapter4_content.py`

- [ ] **Step 1: Record stable implementation-status labels**

Use this exact vocabulary throughout the content model:

```python
IMPLEMENTED = "Implemented"
CONFIGURABLE = "Implemented and configurable"
OPTIONAL = "Optional"
EXPERIMENTAL = "Experimental or evaluation-oriented"
PLANNED = "Planned or future extension"
```

- [ ] **Step 2: Record verified architecture components**

Create component records with `name`, `layer`, `responsibility`, `interfaces`, `persistence`, `dependencies`, and `status`. Include the Vue client, Django routes and views, document services, conversation and summary services, RAG orchestration, extraction and chunking, embeddings, FAISS dense retrieval, BM25 sparse retrieval, fusion, optional reranking, context construction, provider routing, citations, monitoring, evaluation, relational data, file storage, and runtime configuration.

- [ ] **Step 3: Record current data entities and relationships**

Parse `django_app/models.py` and capture exact model and field names for `Notebook`, `Conversation`, `Message`, `QueryLog`, `SuggestedQuestion`, `SystemMetric`, and `ConfigHistory`. Record every verified foreign key, one-to-many relationship, uniqueness rule, timestamp, optional field, and deletion behaviour needed by the ERD and data dictionary.

- [ ] **Step 4: Record interface inputs, outputs, and validation**

Create input records with `screen`, `field`, `type`, `constraint`, `validation`, and `feedback`; create output records with `screen`, `output`, `source`, `timing`, `persistence`, and `purpose`. Derive these from Vue controls, API request parsing, and view-level validation.

- [ ] **Step 5: Verify evidence coverage**

Run:

```powershell
rg -n "class (Notebook|Conversation|Message|QueryLog|SuggestedQuestion|SystemMetric|ConfigHistory)|def (upload_pdf|ask_question|ask_with_citations|summarize_doc)|path\(\"api" app django_app django_backend
rg -n "PDF|question|provider|embedding|retrieval|summary|citation|source" frontend/src/components frontend/src/stores frontend/src/services/api.js
```

Expected: model, view, route, service, and user-interface matches that substantiate every core element planned for the report.

### Task 2: Write the complete Chapter 4 content model

**Files:**
- Modify: `tmp/report_build/chapter4/build_chapter4_content.py`
- Create: `tmp/report_build/chapter4/chapter4_content.json`

- [ ] **Step 1: Define the required chapter hierarchy**

Use these exact numbered headings:

```python
REQUIRED_HEADINGS = [
    "4.1 Introduction",
    "4.2 High-Level Design",
    "4.2.1 System Architecture",
    "4.2.2 User Interface Design",
    "Navigation Design",
    "Input Design",
    "Output Design",
    "4.2.3 Database Design",
    "4.3 AI Component Design",
    "4.4 Software Design",
    "4.5 Summary",
]
```

- [ ] **Step 2: Write the evidence-led narrative**

Write formal paragraphs for every required heading. Explain responsibilities, boundaries, design decisions, alternatives, failure handling, and requirement traceability. Label optional and experimental functionality explicitly; avoid reporting target performance as achieved.

- [ ] **Step 3: Define the report matrices**

Add `input_design`, `output_design`, `entity_dictionary`, and `component_catalogue` arrays. Use stable keys matching Task 1 and ensure every row has a status or implementation note where ambiguity could arise.

- [ ] **Step 4: Define indexing and question-answering pseudocode**

Encode two language-neutral algorithms as arrays of numbered steps. The indexing algorithm must cover validation, safe storage, extraction, page-aware chunking, embedding, dense and sparse indexing, metadata persistence, and status/error reporting. The question-answering algorithm must cover validation, optional source filtering, dense and sparse retrieval, fusion, optional reranking, thresholding, context construction, provider-routed generation, citation packaging, logging, and insufficient-evidence handling.

- [ ] **Step 5: Generate the JSON content model**

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
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tmp/report_build/chapter4/build_chapter4_content.py
```

Expected: `chapter4_content.json` exists, contains every required heading, two complete algorithms, non-empty matrices, and only approved implementation-status labels.

### Task 3: Generate the academic design diagrams

**Files:**
- Create: `tmp/report_build/chapter4/generate_chapter4_diagrams.py`
- Create: `tmp/report_build/chapter4/diagrams/layered_architecture.png`
- Create: `tmp/report_build/chapter4/diagrams/indexing_and_qa_workflow.png`
- Create: `tmp/report_build/chapter4/diagrams/navigation_flow.png`
- Create: `tmp/report_build/chapter4/diagrams/entity_relationship.png`
- Create: `tmp/report_build/chapter4/diagrams/ai_component_pipeline.png`
- Create: `tmp/report_build/chapter4/diagrams/software_components.png`
- Create: `tmp/report_build/chapter4/diagrams/upload_indexing_sequence.png`
- Create: `tmp/report_build/chapter4/diagrams/question_answering_sequence.png`

- [ ] **Step 1: Implement shared visual tokens and helpers**

Use a white background, dark navy `#183B56`, muted blue `#4F81BD`, pale blue `#EAF2F8`, light grey `#F3F5F7`, dark text `#1F2933`, and connector grey `#66788A`. Use Times New Roman or Liberation Serif, 300 DPI, restrained rounded boxes, consistent arrowheads, and no decorative shadows.

Implement reusable helpers with these signatures:

```python
def draw_box(ax, x, y, width, height, title, body="", fill="#EAF2F8") -> None:
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.018",
        facecolor=fill,
        edgecolor="#183B56",
        linewidth=1.4,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height * 0.67, title, ha="center", va="center", weight="bold", color="#183B56")
    if body:
        ax.text(x + width / 2, y + height * 0.34, body, ha="center", va="center", color="#1F2933", wrap=True)


def draw_arrow(ax, start, end, label="", dashed=False) -> None:
    style = "--" if dashed else "-"
    ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": "#66788A", "lw": 1.3, "linestyle": style})
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2, label, ha="center", va="bottom", fontsize=8, color="#1F2933")


def draw_actor(ax, x, y, label) -> None:
    ax.add_patch(Circle((x, y + 0.07), 0.025, facecolor="white", edgecolor="#183B56", linewidth=1.3))
    ax.plot([x, x], [y + 0.045, y - 0.035], color="#183B56", linewidth=1.3)
    ax.plot([x - 0.035, x + 0.035], [y + 0.015, y + 0.015], color="#183B56", linewidth=1.3)
    ax.plot([x, x - 0.035], [y - 0.035, y - 0.085], color="#183B56", linewidth=1.3)
    ax.plot([x, x + 0.035], [y - 0.035, y - 0.085], color="#183B56", linewidth=1.3)
    ax.text(x, y - 0.11, label, ha="center", va="top", fontsize=9, color="#1F2933")


def save_figure(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
```

- [ ] **Step 2: Draw the layered system architecture**

Show user roles, Vue presentation, Django interfaces, application services, RAG and AI services, persistence, and external LLM providers. Use solid arrows for runtime calls and dashed arrows for configuration or monitoring relationships.

- [ ] **Step 3: Draw the offline and online workflow**

Separate PDF indexing from online question answering, while showing the shared FAISS, BM25, metadata, and provider layers.

- [ ] **Step 4: Draw navigation and entity-relationship diagrams**

The navigation diagram must show the main workspace, source panel, chat, evidence inspection, studio summary, settings, RAG trace, and administrator dashboard. The ERD must use exact model names and verified cardinalities from `django_app/models.py`.

- [ ] **Step 5: Draw the AI, component, and sequence diagrams**

Create one AI pipeline diagram, one software component/package diagram, one upload/indexing sequence, and one source-aware Q&A sequence. Sequence diagrams must distinguish synchronous HTTP responses, background indexing status, optional reranking, provider calls, persistence, and error responses.

- [ ] **Step 6: Render and mechanically inspect all diagrams**

Run:

```powershell
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tmp/report_build/chapter4/generate_chapter4_diagrams.py
```

Expected: eight PNG files, each at least 1800 pixels on its longest side, with non-empty dimensions and no labels outside the image bounds.

### Task 4: Capture or construct the interface evidence

**Files:**
- Read: `frontend/src/App.vue`
- Read: `frontend/src/components/layout/`
- Read: `frontend/src/components/chat/`
- Read: `frontend/src/components/studio/`
- Read: `frontend/src/components/settings/`
- Read: `frontend/src/components/admin/`
- Create: `tmp/report_build/chapter4/ui/main_workspace.png`
- Create: `tmp/report_build/chapter4/ui/admin_or_settings.png`

- [ ] **Step 1: Attempt a local application capture**

Start the existing application with its documented command and use the in-app browser workflow to capture a clean desktop view of the main workspace and one settings or administrative view. Do not submit real prompts to external providers and do not expose secrets or private lecture-note content.

- [ ] **Step 2: Use the deterministic fallback when runtime data blocks capture**

If the application cannot render without unavailable dependencies or private data, generate two labelled `Design view based on implemented Vue components` mock-ups with Pillow. Preserve the implemented layout hierarchy: top bar, sources panel, chat/evidence workspace, studio panel or settings modal, and administrator cards.

- [ ] **Step 3: Verify interface-image readability**

Expected: two 16:9 PNG images at least 1600 pixels wide, containing no personal filenames, credentials, blank broken states, clipped controls, or unreadable body text.

### Task 5: Assemble the formal DOCX

**Files:**
- Create: `tmp/report_build/chapter4/generate_chapter4_report.py`
- Read: `tmp/report_build/chapter4/chapter4_content.json`
- Read: `tmp/report_build/chapter4/diagrams/*.png`
- Read: `tmp/report_build/chapter4/ui/*.png`
- Create: `output/reports/chapter_4_design.docx`

- [ ] **Step 1: Configure the academic style system**

Use A4 portrait, 2.54 cm top/bottom/right margins, 2.8 cm left margin, Times New Roman 12 pt body, 1.5 line spacing, justified paragraphs, 0.5-inch first-line indentation, bold numbered headings, 10 pt captions, a quiet running header, and centred page numbering. Use landscape sections only for diagrams or matrices that would be unreadable in portrait.

- [ ] **Step 2: Implement document helpers**

Implement helpers with these exact signatures:

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


def add_heading(doc: Document, heading: str, level: int) -> None:
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    paragraph.paragraph_format.space_after = Pt(6)
    set_run_font(paragraph.add_run(heading), 13 if level == 1 else 12, bold=True)


def add_figure(doc: Document, path: Path, caption: str, width_inches: float) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.keep_with_next = True
    paragraph.add_run().add_picture(str(path), width=Inches(width_inches))
    caption_paragraph = doc.add_paragraph(style="Caption")
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(caption_paragraph.add_run(caption), 10, italic=True)


def add_table(doc: Document, caption: str, headers, rows, widths, font_size: float) -> None:
    caption_paragraph = doc.add_paragraph(style="Caption")
    caption_paragraph.paragraph_format.keep_with_next = True
    set_run_font(caption_paragraph.add_run(caption), 10, italic=True)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    header_cells = table.rows[0].cells
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for index, header in enumerate(headers):
        header_cells[index].width = Inches(widths[index])
        header_cells[index].text = str(header)
        header_cells[index].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_run_font(header_cells[index].paragraphs[0].runs[0], font_size, bold=True)
    for values in rows:
        cells = table.add_row().cells
        for index, value in enumerate(values):
            cells[index].width = Inches(widths[index])
            cells[index].text = str(value)
            cells[index].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cells[index].paragraphs[0].paragraph_format.space_after = Pt(0)
            set_run_font(cells[index].paragraphs[0].runs[0], font_size)


def add_algorithm(doc: Document, caption: str, steps: list[str]) -> None:
    caption_paragraph = doc.add_paragraph(style="Caption")
    caption_paragraph.paragraph_format.keep_with_next = True
    set_run_font(caption_paragraph.add_run(caption), 10, italic=True)
    for index, step in enumerate(steps, start=1):
        paragraph = doc.add_paragraph(style="List Number")
        paragraph.paragraph_format.left_indent = Inches(0.35)
        paragraph.paragraph_format.first_line_indent = Inches(-0.2)
        paragraph.paragraph_format.space_after = Pt(3)
        set_run_font(paragraph.add_run(step), 11)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, end])
    set_run_font(run, 10)
```

Tables must use explicit widths, repeated header rows, content-based alignment, consistent cell margins, and expandable row heights. Figures and captions must remain together where possible.

- [ ] **Step 3: Assemble all narrative and visuals in guideline order**

Insert the chapter title, all required sections, eight diagrams, two interface figures, the four matrices, entity data dictionary, and two algorithms. Introduce every figure or table in the preceding prose and interpret its design significance afterward.

- [ ] **Step 4: Save clean document metadata**

Set title `Chapter 4 - Design`, subject `AI-Based Lecture Note Question Answering System Using Retrieval-Augmented Generation`, blank author, and keywords `RAG, lecture notes, system design, artificial intelligence, Django, Vue`.

- [ ] **Step 5: Generate the DOCX**

Run:

```powershell
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tmp/report_build/chapter4/generate_chapter4_report.py
```

Expected: `output/reports/chapter_4_design.docx` exists, is non-empty, and opens as a valid OOXML package.

### Task 6: Add deterministic structural validation

**Files:**
- Create: `tmp/report_build/chapter4/validate_chapter4_report.py`
- Read: `tmp/report_build/chapter4/chapter4_content.json`
- Read: `output/reports/chapter_4_design.docx`

- [ ] **Step 1: Validate content invariants**

Assert that all required headings, algorithms, matrices, status labels, figure captions, table captions, and component names are present. Reject empty values, duplicate captions, unresolved markers, unsupported performance claims, and mismatches between ERD entities and the data dictionary.

- [ ] **Step 2: Validate DOCX package structure**

Use `python-docx` and `zipfile` to assert that all required headings and captions occur in the document, at least ten visual assets exist under `word/media/`, tables contain non-empty header rows, the document uses A4 sections, and metadata contains no personal author value.

- [ ] **Step 3: Run validation**

Run:

```powershell
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tmp/report_build/chapter4/validate_chapter4_report.py
```

Expected: exit code 0 with counts for eleven required headings, at least ten figures, at least four tables, two algorithms, and complete media coverage.

### Task 7: Render, inspect, and refine every page

**Files:**
- Read: `output/reports/chapter_4_design.docx`
- Create: `tmp/report_build/chapter4/render/page-*.png`
- Create: `tmp/report_build/chapter4/render/chapter_4_design.pdf`

- [ ] **Step 1: Render DOCX to PNG and PDF**

Run:

```powershell
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\wongs\.codex\plugins\cache\openai-primary-runtime\documents\26.619.11828\skills\documents\render_docx.py' `
  'output\reports\chapter_4_design.docx' `
  --output_dir 'tmp\report_build\chapter4\render' --emit_pdf
```

Expected: one PNG per report page and a non-empty renderer-produced PDF.

- [ ] **Step 2: Inspect every rendered page at full resolution**

Check title treatment, margins, headings, body rhythm, page numbering, every diagram, every interface image, captions, matrices, algorithms, landscape transitions, orphan control, table continuation, missing glyphs, and header/footer collisions.

- [ ] **Step 3: Correct every visible defect**

Adjust figure dimensions, paragraph keep rules, line spacing, table widths, font size, cell margins, section breaks, page breaks, or diagram labels in the generator files. Regenerate the DOCX, rerun structural validation, and rerender after every meaningful correction.

- [ ] **Step 4: Publish the matching PDF**

Copy the latest renderer-produced PDF to `output/reports/chapter_4_design.pdf` and confirm that its page count matches the DOCX render.

### Task 8: Final verification and handoff

**Files:**
- Read: `output/reports/chapter_4_design.docx`
- Read: `output/reports/chapter_4_design.pdf`

- [ ] **Step 1: Run final mechanical verification**

Run:

```powershell
& 'C:\Users\wongs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tmp/report_build/chapter4/validate_chapter4_report.py
Get-Item output/reports/chapter_4_design.docx,output/reports/chapter_4_design.pdf
```

Expected: validator exit code 0 and both files have non-zero sizes.

- [ ] **Step 2: Confirm report-design consistency**

Verify that the latest visual review has no defects, figure and table numbering is contiguous, all design claims are evidence-backed, optional capabilities remain labelled, terminology matches Chapters 2 and 3, and stable final filenames are present.

- [ ] **Step 3: Deliver the report**

Provide clickable links to the final DOCX and PDF and summarize the included sections, diagrams, interface evidence, and completed visual verification.
