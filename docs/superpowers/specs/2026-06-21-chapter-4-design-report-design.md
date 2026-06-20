# Chapter 4 Design Report Design

## Objective

Create a comprehensive academic Chapter 4 report for the project titled **AI-Based
Lecture Note Question Answering System Using Retrieval-Augmented Generation
(RAG)**. The chapter will follow the supplied Chapter 4 design guideline, continue
the presentation conventions established by Chapters 2 and 3, and describe the
current repository accurately.

## Deliverables

- Editable Microsoft Word document (`.docx`)
- Matching portable document (`.pdf`)
- Approximately 18-25 pages, adjusted as needed for readable diagrams and tables
- Standalone Chapter 4 with numbered headings matching the guideline
- Architecture, navigation, data, AI, and interaction diagrams where they improve
  technical clarity
- Visually verified output with no clipped text, broken tables, orphaned headings,
  missing glyphs, or inconsistent page furniture

## Evidence Base

The report will use the following sources in priority order:

1. `C:\Users\wongs\Downloads\chapter 4.pdf` for the required chapter structure.
2. Current source code and configuration for implemented components, interfaces,
   algorithms, data entities, validation rules, and persistence.
3. Existing Chapter 2 and Chapter 3 reports for terminology, scope, numbering, and
   academic presentation conventions.
4. Current repository documentation and approved design records for architectural
   intent and configurable or planned capabilities.
5. Existing tests and evaluation artifacts to distinguish verified behaviour from
   optional, experimental, or future work.

Current code takes precedence when older documents conflict with implementation.
Repository evidence will be presented as project design evidence rather than as
external scholarly literature.

## Report Structure

### Chapter title

**CHAPTER 4: DESIGN**

### 4.1 Introduction

Preview the chapter and explain how the requirements established in Chapter 3 are
translated into a modular system design. Introduce the high-level architecture,
interface, data, AI component, and software design sections.

### 4.2 High-Level Design

Describe the end-to-end layered architecture and the separation between the Vue
client, Django API, RAG services, retrieval and generation components, persistence,
and optional external providers.

#### 4.2.1 System Architecture

Include a layered architecture diagram covering:

- User and administrator interaction
- Vue/Vite presentation layer
- Django REST and WebSocket interface layer
- Application services for document management, chat, summaries, suggestions,
  configuration, monitoring, and evaluation
- RAG orchestration, PDF loading, chunking, embeddings, dense and sparse retrieval,
  fusion, optional reranking, context construction, and answer generation
- FAISS, BM25, SQLite, uploaded PDFs, configuration files, and evaluation artifacts
- Gemini, OpenRouter, and local llama.cpp-compatible generation providers

Explain the principal boundaries, responsibilities, and data movement. Include a
second process-oriented diagram showing the offline document-indexing path and the
online question-answering path.

#### 4.2.2 User Interface Design

Describe the current user-facing and administrative interface as a responsive web
application. Cover the document/source panel, chat workspace, citation and evidence
display, studio or summary functions, settings, theme controls, RAG demonstration,
and administrative monitoring views where supported by current code.

Use current application screenshots if the application can be started reliably with
available local data. If a view cannot be rendered without unavailable external
services, use a clearly labelled interface design mock-up based on the implemented
Vue component structure.

##### Navigation Design

Present a navigation-flow diagram showing the main workspace, document selection,
question-answering flow, source inspection, summary generation, settings, RAG trace,
and administrator dashboard. Explain global, contextual, modal, and evidence-linked
navigation controls.

##### Input Design

Describe PDF upload, question entry, document selection, source filtering, summary
configuration, provider/model selection, embedding selection, retrieval settings,
and administrative search or debugging inputs. Include a compact input-validation
matrix with field, type, constraint, validation behaviour, and feedback.

##### Output Design

Describe generated answers, citations, source snippets, retrieved chunks, summaries,
question suggestions, upload/indexing status, configuration and health feedback,
dashboard metrics, evaluation results, and error messages. Classify outputs as
interactive, on-demand, operational, or persisted rather than inventing periodic
reporting that the system does not implement.

#### 4.2.3 Database Design

Introduce the hybrid persistence strategy: relational operational data in SQLite,
retrieval data in FAISS and BM25 structures, uploaded PDF files, and JSON-based
runtime configuration or histories where applicable.

Include an entity-relationship diagram for the current Django models, centred on
Notebook, Conversation, Message, QueryLog, SuggestedQuestion, SystemMetric, and
ConfigHistory. State cardinalities and business rules explicitly. Add a focused data
dictionary for the principal entities and explain normalization, integrity,
retention, and the boundary between relational and vector data.

### 4.3 AI Component Design

Describe the lecture-note dataset as a user-supplied, evolving document corpus rather
than a fixed training dataset. Explain supported metadata, preprocessing assumptions,
representative evaluation questions, reference answers where available, and the
limitations of scanned or visually complex PDFs.

Document the complete RAG design:

1. PDF validation and extraction
2. Page-aware text preparation and chunking
3. Sentence-transformer embedding generation
4. FAISS dense indexing and retrieval
5. BM25 sparse indexing and retrieval
6. Reciprocal-rank or weighted fusion
7. Optional cross-encoder reranking
8. Similarity filtering and top-k selection
9. Context construction and provider-independent prompting
10. Grounded answer generation with visible source evidence
11. RAGAS and human evaluation feedback

Include an AI-component diagram and concise pseudocode for document indexing and
question answering. Explain design parameters and failure handling without claiming
unverified accuracy or latency results.

### 4.4 Software Design

Describe the modular software organization and the responsibilities of the principal
packages and services. Include:

- A component or package diagram for frontend, Django views, application services,
  retrieval, evaluation, persistence, and providers
- A sequence diagram for PDF upload and indexing
- A sequence diagram for source-aware question answering
- Design patterns such as service separation, provider routing, configuration-driven
  behaviour, shared-state locking, explicit error responses, and asynchronous status
  reporting
- Security, privacy, reliability, maintainability, and deployment considerations
  that materially influence the design

CRISP-DM may be referenced only as an organizing lifecycle where useful; this
section will focus on implemented software design rather than repeat the Chapter 3
analysis process.

### 4.5 Summary

Synthesize how the proposed architecture, interface, persistence model, AI pipeline,
and software modules satisfy the established requirements. Conclude with the next
activities: implementation completion, integration testing, usability validation,
retrieval tuning, RAG evaluation, and deployment preparation.

## Planned Visuals and Tables

1. Layered system architecture diagram
2. Offline indexing and online question-answering workflow
3. Main user-interface screenshot or implementation-grounded mock-up
4. Navigation-flow diagram
5. Input-validation matrix
6. Output-design matrix
7. Entity-relationship diagram
8. Principal-entity data dictionary
9. AI component and RAG algorithm diagram
10. PDF upload and indexing sequence diagram
11. Source-aware question-answering sequence diagram
12. Software component/package diagram

Figures and tables will be numbered in order, remain legible at A4 report scale,
and be introduced and interpreted in the surrounding prose. Tables will use repeated
headers when split across pages and content-driven column widths.

## Writing and Presentation Style

- Formal academic English with concise, evidence-led explanations
- A4 portrait layout with conventional university-report margins
- Times New Roman 12 pt body text, 1.5 line spacing, and justified paragraphs
- Bold numbered headings that follow the supplied guideline
- Quiet running header and page numbering consistent with Chapters 2 and 3
- Restrained black, grey, and dark-blue diagram palette
- Limited bullet use outside algorithms, validation rules, and genuine lists
- Captions placed consistently below figures and above or below tables according to
  the established report convention

## Accuracy Rules

- Distinguish implemented, configurable, optional, experimental, and planned
  capabilities.
- Do not present API routes or UI controls as available solely because they appear in
  old documentation; verify them against current code.
- Do not claim measured accuracy, latency, recall, RAGAS performance, scalability, or
  usability unless supported by current artifacts.
- Do not expose credentials, secrets, private document content, or personal data.
- Keep terminology consistent with Chapters 2 and 3, especially for users, sources,
  chunks, retrieval, citations, providers, and evaluation metrics.
- Ensure diagrams, text, tables, model relationships, and pseudocode describe the
  same design.

## Verification

1. Cross-check every component and interaction against current source code,
   configuration, models, routes, and tests.
2. Validate database entities, field names, relationships, and persistence boundaries
   against Django models and retrieval storage.
3. Confirm UI descriptions against current Vue components and a locally rendered
   application where possible.
4. Scan for placeholders, unsupported claims, duplicated explanations, mismatched
   captions, and inconsistent terminology.
5. Verify that all pseudocode matches the actual high-level control flow without
   reproducing unnecessary implementation detail.
6. Render the final DOCX to PNG and inspect every page at full size.
7. Export the matching PDF and verify page count, tables, diagrams, screenshots,
   headers, footers, and page breaks.
