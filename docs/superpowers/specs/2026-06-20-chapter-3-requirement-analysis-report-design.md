# Chapter 3 Requirement Analysis Report Design

## Objective

Create a formal academic Chapter 3 report for the project titled **AI-Based
Lecture Note Question Answering System Using Retrieval-Augmented Generation
(RAG)**. The chapter will follow the supplied requirement-analysis guideline
and describe the current repository accurately without presenting unverified
experimental results as completed findings.

## Deliverables

- Editable Microsoft Word document (`.docx`)
- Matching portable document (`.pdf`)
- Standalone Chapter 3 with numbered headings matching the guideline
- Diagrams, requirement tables, and a data dictionary where they materially
  improve clarity
- Visually verified output with no clipped text, broken tables, orphaned
  headings, missing glyphs, or inconsistent page furniture

## Evidence Base

The report will use the following sources in priority order:

1. The supplied `chapter3 guideline.pdf` for mandatory chapter structure.
2. Current application code and configuration for implemented behaviour,
   interfaces, persisted data, validation rules, and dependencies.
3. Current repository documentation and approved design records for system
   purpose, architecture, workflows, and measurable quality targets.
4. Existing tests to distinguish verified behaviour from planned or optional
   capabilities.

Repository evidence is descriptive project evidence rather than scholarly
literature. No feature will be described as implemented solely because it
appears in an outdated proposal.

## Report Structure

### Chapter title

**CHAPTER 3: REQUIREMENT ANALYSIS**

### 3.1 Introduction

Preview the purpose of the analysis phase, explain how the chapter converts
the identified educational problem into system requirements, and outline the
sections that follow.

### 3.2 Problem Analysis

Describe the current lecture-note study scenario, including manual document
search, fragmented navigation across PDFs, keyword-search limitations,
time-consuming synthesis, and the risk of unsupported answers from generic
language models.

Present the proposed problem-solving process as an adapted CRISP-DM workflow:
project understanding, lecture-note data understanding, PDF extraction and
text preparation, RAG modelling and application development, technical and
functional evaluation, and deployment with iterative refinement.

Include a current-scenario activity diagram showing how a student manually
searches lecture materials and a proposed high-level workflow showing how the
RAG system shortens that process. Quantitative values will be treated as
design parameters or target requirements unless verified by completed
evaluation artifacts.

### 3.3 Requirement Analysis

#### 3.3.1 Data Requirement

Describe required inputs, interfaces, transformations, storage, and outputs:

- PDF lecture notes and associated filename/page metadata
- User questions, optional source filters, and conversation context
- Extracted text chunks, embeddings, FAISS index data, and retrieval scores
- Generated answers, source snippets, citations, summaries, and suggestions
- Application settings, RAG configuration, query logs, system metrics,
  configuration history, and conversation records

Include a data-flow description and a data dictionary identifying each data
element, type or format, source, purpose, storage location, and validation or
retention rule. Sensitive credentials will be identified as environment
configuration and will not be reproduced.

#### 3.3.2 Functional Requirement

Specify uniquely identified functional requirements covering:

- PDF validation, upload, storage, parsing, chunking, embedding, and indexing
- Source listing, filtering, selection, and index management
- Question submission, hybrid or dense retrieval, context construction,
  answer generation, and source-transparent responses
- Conversation history and multi-turn interaction
- Document summarisation and question suggestions
- Runtime provider, embedding-model, and retrieval configuration
- Evaluation, monitoring, health checks, and error reporting

Include a use-case diagram with the Student/User as the primary actor and the
System Administrator or Maintainer as a supporting actor. Add a functional
requirements table containing ID, requirement statement, actor, input,
processing, output, and acceptance criterion. Optional or experimental
features will be labelled clearly.

#### 3.3.3 Non-functional Requirement

Define measurable quality requirements for usability, performance, answer
quality, reliability, security, privacy, maintainability, compatibility,
scalability, availability, and accessibility. Targets will include file-size
limits, response-time or timeout expectations, retrieval-quality goals, test
and logging expectations, safe filename handling, credential protection, and
browser compatibility where supported by repository evidence.

Each requirement will receive a unique identifier and verification method.
Unmeasured targets will be phrased as acceptance criteria for later testing,
not as achieved results.

#### 3.3.4 Other Requirement

List and justify the software and hardware needed to develop, operate, and
evaluate the system. Software coverage will include Python, Django, Vue/Vite,
sentence-transformers, FAISS, BM25/hybrid retrieval components, SQLite,
supported hosted or local LLM providers, pytest, and optional Redis.

Hardware coverage will distinguish a minimum cloud-LLM configuration from a
recommended local-inference configuration, including CPU, RAM, storage,
optional GPU, and network requirements. Other operational constraints will
cover text-readable PDFs, API credentials when required, dataset ownership,
privacy, copyright, backups, and human evaluation data.

### 3.4 Summary

Summarise the problem analysis and the established data, functional,
non-functional, software, and hardware requirements. Conclude with a clear
transition to the next development activity: detailed design, implementation,
integration, and systematic evaluation.

## Diagrams and Tables

The chapter will contain the following visual evidence:

1. Current manual lecture-note search activity diagram.
2. Proposed RAG system context or workflow diagram.
3. System use-case diagram.
4. Data dictionary table.
5. Functional requirements matrix.
6. Non-functional requirements matrix.
7. Software and hardware requirements tables.

Diagrams will use restrained academic styling, remain legible at A4 report
scale, and include numbered captions. Tables may continue across pages with
repeated header rows and content-driven column widths.

## Writing and Presentation Style

- Formal academic English with concise, evidence-led paragraphs
- A4 portrait layout with conventional university-report margins
- Times New Roman 12 pt body text, 1.5 line spacing, and justified paragraphs
- Bold numbered headings that follow the supplied guideline
- Quiet running header and page numbering suitable for a standalone chapter
- Restrained black, grey, and dark-blue visual palette
- Limited bullet use outside requirement lists and genuine tabular content

## Accuracy Rules

- Distinguish implemented, configurable, optional, experimental, and planned
  capabilities.
- Do not report target latency, accuracy, recall, or RAGAS values as achieved
  unless supported by current evaluation artifacts.
- Do not expose secrets, local credentials, or personal data.
- Resolve conflicts between old documentation and current code in favour of
  current code, noting material limitations where relevant.
- Keep requirement identifiers stable and ensure every acceptance criterion is
  objectively testable.
- Avoid citations to internal files as though they were external scholarly
  sources; describe them as project evidence where attribution is useful.

## Verification

1. Cross-check every functional requirement against current views, services,
   configuration, models, or tests.
2. Validate data entities and storage descriptions against Django models,
   configuration files, FAISS persistence, and conversation services.
3. Confirm all diagrams use the same actors, system boundary, and terminology
   as the requirement tables.
4. Scan for placeholders, unsupported claims, inconsistent requirement IDs,
   and mismatched captions or cross-references.
5. Render the final DOCX to PNG and inspect every page at full size.
6. Export a matching PDF and verify page count, tables, diagrams, headers,
   footers, and page breaks.
