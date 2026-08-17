# DSH Academic Report Plugin Design

## Purpose

Add an out-of-tree DeepSeek Harness (`desktop` profile) plugin for a UTeM product-based Final Year Project report. It writes one reviewed chapter at a time, rather than an entire report in one request.

## Scope

- Maintain project metadata, chapter state, APA 7 sources, and output paths.
- Generate one selected chapter as a reviewable draft.
- Require explicit user approval before inserting a chapter into a working template copy.
- Preserve `fyp/Template PSM Report 2025 v2 - Product-based.docx` unchanged.
- Reuse the template's A4 layout, Times New Roman typography, `Body Text 2` body style, chapter headings, lists, captions, and front matter.
- Record the metadata required for APA 7 in-text citations and References.

## Non-goals

- Generating an entire report in one request.
- Inventing academic sources, results, student data, or claims.
- Publishing a final submission without the user's review.
- Requiring external cloud citation services.

## User Workflow

1. Start a report and enter project title, student name, supervisor, course year, topic, and target chapter.
2. Add verified sources with DOI or URL and bibliographic metadata.
3. Request a chapter draft; the agent marks missing facts clearly instead of inventing them.
4. Review the draft and either revise or approve it.
5. On approval, place the chapter in a working template copy and update report state.
6. Repeat for later chapters, then compile References from approved source records only.

## DSH Integration

The plugin is installed as an out-of-tree dependency of `C:\\Users\\wongs\\.dsh\\profiles\\desktop` and mounted through that profile's patch configuration. It provides:

- an `academic_report` model-facing tool to initialize a report, draft one chapter, register sources, inspect status, and apply an approved chapter;
- a prompt section containing the workflow rules and UTeM template constraints;
- JSON files in the selected workspace for durable report state and source provenance.

The tool returns an approval-needed result instead of editing a DOCX when approval is absent. It also refuses to apply a chapter that has unresolved citations or required factual placeholders.

## Workspace Files

```text
fyp/
  academic-report.json          # project metadata, chapter state, source records
  drafts/
    chapter-01.md               # generated draft awaiting or carrying approval
  output/
    <report-name>-working.docx  # copy derived from the retained template
```

The original template remains read-only. Drafts are Markdown for easy review; only approved drafts affect the working DOCX.

## Template Fidelity

The reference has 20 A4 portrait sections with a 1.57-inch left margin and 0.98-inch top, right, and bottom margins. It includes front matter, automatic content/list fields, six chapters, References, and Appendices. The working copy must preserve its existing styles, fields, headers, footers, images, and relationships unless an approved chapter changes them.

The template was structurally inspected, including its content controls. LibreOffice is not installed on this computer, so automatic PDF/image rendering is unavailable. The plugin reports that preflight status and can perform structural checks; after LibreOffice is installed, rendering and image review become a final QA gate.

## Error Handling

- Missing project information: use labelled placeholders in the draft, never invented facts.
- Missing citation metadata: block chapter approval and state what is needed.
- Missing or changed template: refuse to apply the chapter and preserve all outputs.
- Locked Word file: save the approved draft, report the lock, and make no DOCX change.
- Missing LibreOffice: allow drafting and structural validation but report pending visual QA.

## Verification

- Unit tests cover report initialization, action validation, chapter state transitions, citation validation, and refusal paths.
- A fixture report proves an unapproved draft cannot be applied.
- Installation is checked against the `desktop` profile configuration.
- The working DOCX is structurally audited; when LibreOffice is available, it is rendered and every page image is reviewed before delivery.
