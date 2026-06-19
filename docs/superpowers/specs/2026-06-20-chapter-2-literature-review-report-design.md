# Chapter 2 Literature Review Report Design

## Objective

Create a comprehensive academic Chapter 2 report for the project titled **AI-Based Lecture Note Question Answering System Using Retrieval-Augmented Generation (RAG)**. The report will follow the supplied Chapter 2 guideline while omitting the project methodology section at the user's request.

## Deliverables

- Editable Microsoft Word document (`.docx`)
- Matching portable document (`.pdf`)
- Approximately 15-20 pages, excluding references where necessary
- APA 7 in-text citations and reference list
- Visually verified output with no clipped text, broken tables, orphaned headings, or inconsistent page furniture

## Evidence Base

The report will use the following sources in priority order:

1. `fyp/03-literature/literature_review_ranked_by_relevance.xlsx` for study ranking, relevance, methods, reported results, advantages, and limitations.
2. Corresponding journal PDFs in `fyp/03-literature/journal/` to verify bibliographic details and substantive claims.
3. The repository's source code and current project documentation to describe the implemented system accurately.
4. Foundational references only when required to define core concepts not adequately covered by the supplied literature set.

The highest-ranked studies will carry the main argument. Medium-ranked studies may be used selectively for contrast or alternative techniques. Low-ranked and very-low-ranked studies will not be included unless they clarify a specific rejected alternative. Paper #24 will not be treated as a separate independent study because the workbook identifies it as a duplicate of paper #9.

## Report Structure

### Chapter title

**CHAPTER 2: LITERATURE REVIEW AND PROJECT PLANNING**

### 2.1 Introduction

Preview the purpose, scope, thematic organization, and relationship between the literature review and the proposed lecture-note question-answering system.

### 2.2 Facts and Findings

#### 2.2.1 Domain

Explain the intersection of educational technology, natural language processing, information retrieval, document question answering, large language models, and retrieval-augmented generation. Establish why lecture notes require document-grounded answers and source transparency.

#### 2.2.2 Existing Systems

Review the most relevant systems and studies, led by:

- Textbook question answering using LLMs and RAG
- ICCA-RAG sparse-dense document QA
- Higher-education RAG chatbot integration
- UQA-RAG semantic and BM25 hybrid retrieval
- Customized EDA documentation QA with retrieval tuning and reranking
- Long-context RAG and question-answer matching systems where useful

Include a comparison table covering domain, data/input, retrieval approach, generator, evaluation/result, advantages, limitations, and relevance to the project. The prose will synthesize recurring findings instead of repeating the table row by row.

#### 2.2.3 Techniques

Organize the technical review around the RAG pipeline:

1. PDF text extraction and document segmentation
2. Fixed, recursive, sentence-aware, and semantic chunking
3. Dense sentence embeddings
4. Sparse BM25 retrieval
5. Hybrid retrieval and reciprocal-rank/weighted fusion
6. FAISS and alternative vector-index structures
7. Cross-encoder reranking
8. Prompted generation with local or hosted LLMs
9. Citation grounding and source transparency
10. RAG evaluation using faithfulness, answer relevancy, context precision, and context recall

Include a technique comparison table with strengths, weaknesses, computational implications, suitability for lecture notes, and adoption status in the project. Discuss applicable alternatives that were not selected, including full long-context prompting, cloud vector databases, knowledge-graph RAG, multimodal segmentation, extensive model fine-tuning, and generated-question indexing.

### Methodology omission

The guideline's project methodology section will be omitted completely. Subsequent guideline sections will retain their original numbering so the report remains traceable to the supplied rubric.

### 2.4 Project Requirements

#### 2.4.1 Software Requirements

List and briefly justify the implemented software stack, including Python, Django, Django REST Framework, Vue 3, Vite, Tailwind CSS, sentence-transformers, FAISS, LangChain/LlamaIndex components, BM25, RAGAS, SQLite, pytest, optional Redis, and supported LLM providers.

#### 2.4.2 Hardware Requirements

Provide practical minimum and recommended configurations. Distinguish cloud-LLM use from local llama.cpp inference. Cover processor, RAM, optional GPU, storage, and network connectivity without claiming hardware that the repository does not require.

#### 2.4.3 Other Requirements

Cover access to lecture-note PDFs, API credentials when hosted models are used, privacy and copyright considerations, internet connectivity, a suitable development environment, test data, and human review for evaluation.

### 2.5 Project Schedule and Milestones

Use the existing 16-week project plan:

- Weeks 1-3: Core RAG pipeline
- Weeks 4-5: LLM integration
- Weeks 6-7: API development
- Weeks 8-10: Vue user interface
- Weeks 11-12: Advanced features and citation support
- Weeks 13-14: Testing and optimization
- Weeks 15-16: Documentation and deployment preparation

Include a one-page Gantt chart and short milestone explanations.

### 2.6 Summary

Synthesize the main evidence, explain how it supports the selected hybrid RAG architecture, state the principal design trade-offs, and transition to the next report chapter without describing methodology.

### References

Use APA 7 formatting. Every in-text citation must have a matching reference entry, and every reference entry must be cited. Journal metadata will be verified from the PDF itself wherever extractable.

## Writing and Presentation Style

- Formal academic English with clear topic sentences and evidence-led paragraphs
- Critical synthesis rather than a sequence of isolated paper summaries
- Restrained use of bullets outside requirement lists
- Tables only for genuine comparisons
- Consistent numbered headings matching the guideline
- A4 portrait layout, Times New Roman 12 pt body text, 1.5 line spacing, justified paragraphs, and conventional university-report margins
- Page numbers and a quiet running header appropriate for a multi-page academic chapter

## Accuracy Rules

- Do not claim that a feature is implemented solely because it appears in an old proposal; confirm it in current code or current documentation.
- Label optional, experimental, or future techniques explicitly.
- Report literature metrics exactly as stated in the source and preserve their evaluation context.
- Do not combine results from different datasets as if they were directly comparable.
- Do not cite the ranking workbook as a scholarly source; cite the underlying papers.
- Do not include methodology content under another heading.

## Verification

1. Check all selected journal PDFs against the spreadsheet metadata.
2. Cross-check project requirements and implemented techniques against the repository.
3. Validate citation-reference consistency and remove placeholders.
4. Render the final DOCX to PNG and inspect every page.
5. Export a matching PDF and confirm page count, tables, Gantt chart, headers, footers, and references render correctly.
