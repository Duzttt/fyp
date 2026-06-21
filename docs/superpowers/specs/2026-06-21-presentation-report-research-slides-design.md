# Presentation Report Research Slides Design

## Goal

Revise `presentation/index.html` into a concise 18-slide academic-defense deck
for a 15-minute presentation. Strengthen the existing problem statement and
objectives, add project scope, summarize the top three studies from the ranked
literature-review materials, present the adapted methodology as a flowchart,
and visualize actual project evaluation results with a suitable graph.

## Approved Direction

Use a compact academic narrative and the evidence-first editorial visual style.
The deck retains its warm cream background, amber accent, serif headings, and
restrained motion. New research slides must look native to the existing deck,
not like a second theme inserted into it.

## Presentation Structure

The final deck contains these 18 slides:

1. Title
2. Problem Statement
3. Project Objectives
4. Project Scope and Boundaries
5. Literature Review — Top Three Studies
6. Research Gap and Project Contribution
7. Methodology — six-stage flowchart
8. System Architecture and Technology Stack
9. PDF Ingestion and Indexing
10. Retrieval and Answer-Generation Flow
11. Core Technical Design — chunking, embeddings, BM25, and FAISS
12. Interface and User Workflow
13. Chat Demonstration
14. Evaluation Method — RAGAS metrics
15. Results — actual comparison graph
16. Findings and Discussion
17. Limitations and Future Work
18. Conclusion

Existing technical slides may be merged or rewritten to preserve this count and
avoid repetition. The existing Problem and Project Objectives slides are
replaced rather than duplicated.

## Content Design

### Problem Statement

Present three connected problems:

- Students face information overload across long and numerous lecture notes.
- Manual searching is slow and makes it difficult to locate precise supporting
  passages.
- Generic AI assistants can answer without grounding in the student's approved
  lecture material, reducing trust and traceability.

The slide ends with one concise need statement: students require fast,
source-grounded answers drawn from their own lecture notes.

### Project Objectives

Use four measurable objectives:

1. Ingest PDF lecture notes while preserving source and page metadata.
2. Retrieve relevant passages through hybrid dense and keyword search.
3. Generate answers grounded in retrieved evidence and display citations or
   source snippets.
4. Evaluate retrieval, answer quality, functionality, and practical response
   performance.

### Scope and Boundaries

The in-scope column includes PDF upload, extraction, chunking, embedding,
FAISS/BM25 hybrid retrieval, configurable LLM generation, cited answers, the
web interface, and RAGAS-based evaluation.

The out-of-scope column includes non-PDF learning sources, automatic grading,
course-authoring tools, institution-wide LMS integration, and claims of
universal subject expertise.

### Literature Review

Use the top three entries from the project's ranked literature-review
materials. Each study card contains:

- a short author-year citation and title;
- the method or system approach;
- the most relevant verified finding;
- one verified limitation; and
- its relevance to this project.

Only claims confirmed by the ranking workbook and corresponding journal source
may be used. The slide does not attempt to summarize every journal.

### Research Gap and Contribution

Synthesize the three studies into a single gap: educational QA research often
demonstrates useful retrieval or generation, but practical lecture-note systems
still need stronger source traceability, hybrid retrieval, local or configurable
model support, and integrated evaluation. Present this project's contribution as
an implementation response to that gap without claiming research novelty beyond
the available evidence.

### Methodology

Use an adapted six-stage CRISP-DM flow:

1. Project and Problem Understanding
2. Lecture-Note Data Understanding
3. PDF Extraction and Text Preparation
4. RAG Modelling and Application Development
5. Technical and Functional Evaluation
6. Deployment and Iterative Refinement

Display the stages as numbered, connected boxes with short activity labels. A
secondary feedback connector returns from evaluation and refinement to earlier
preparation and modelling stages.

### Evaluation Graph

Use actual repository evaluation results to compare the relevant experiment
configurations, expected to include baseline, smart chunking, and enhanced
retrieval where the datasets are comparable. Plot the four RAGAS dimensions:
faithfulness, answer relevancy, context precision, and context recall.

Use a grouped bar chart with a zero-to-one scale, direct numeric labels, a
compact legend, and one or two evidence-based interpretation callouts. Do not
combine metrics from incompatible evaluation sets or imply causal improvement
when the available data supports only an observed association.

## Visual Design

- Preserve the current 16:9 full-viewport presentation format.
- Use the existing typography and warm editorial color tokens.
- Use three equal cards for the literature slide, with clear internal labels.
- Use restrained amber connectors and pale surfaces for the methodology flow.
- Use amber, sage, and neutral grey as the graph series colors.
- Keep body text presentation-sized; detailed prose belongs in speaker notes or
  the source report, not on the slide.
- Retain the existing progress bar, slide counter, keyboard navigation, click
  navigation, touch navigation, and animation language.

## Evidence Sources

Content must be derived from the current repository, prioritizing:

- the ranked literature-review workbook and matched journal PDFs;
- `PROJECT_PROPOSAL.md` and `PROJECT_CONTEXT.md`;
- current RAG service and retrieval source files;
- `ragas_analysis_report.md` and the evaluation CSV files; and
- existing methodology and architecture documentation.

Proposal-only capabilities must not be described as implemented. Unverified
journal claims and unsupported benchmark numbers must be omitted or clearly
qualified.

## Implementation Boundaries

- Modify the single presentation file and reuse existing local assets where
  appropriate.
- Do not add a frontend framework or external chart dependency.
- Build the flowchart and graph with semantic HTML/CSS or inline SVG so the deck
  remains portable.
- Do not modify backend application behavior as part of this presentation task.
- Preserve unrelated working-tree changes.

## Verification

Before completion:

1. Confirm exactly 18 slides and correct slide-counter behavior.
2. Confirm all required topics are present and existing problem/objective content
   is not duplicated.
3. Cross-check the three literature cards against their source evidence.
4. Recalculate graph values from the selected comparable evaluation files.
5. Open the presentation in a browser and exercise keyboard, click, and touch
   navigation.
6. Inspect every slide at common 16:9 desktop sizes for clipping, overlap,
   contrast, and readable labels.
7. Confirm the browser console has no presentation-related errors.

## Acceptance Criteria

The result is an 18-slide, 15-minute academic presentation with a coherent
problem-to-evidence narrative, three source-verified literature studies, an
adapted methodology flowchart, and a readable graph based on real project data.
It retains the existing visual identity and navigation while removing redundant
technical detail.
