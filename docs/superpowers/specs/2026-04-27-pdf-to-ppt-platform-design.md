# PDF To Editable PPT Platform Design

Date: 2026-04-27

## Summary

This project is a Web platform for AI-assisted workflows. The first workflow is PDF to editable PPT conversion. The MVP includes the platform skeleton, local account/password auth, asynchronous workflow dispatch, a Worker container, one Runner Agent, one Validator Agent, and a task page where the user can continue chatting with the AI to improve the result.

The PDF to PPT output must not be a deck of full-page screenshots. The target is a PPTX that visually matches the PDF as closely as possible while preserving editable PowerPoint elements such as text boxes, images, shapes, tables, and paths. Raster fallback is allowed only for bounded regions that cannot yet be reconstructed reliably, and it must be measured and reported.

WPS-style conversion is treated as a reference and optional provider. If WPS integration requires expensive authorization, third-party upload, or a hard-to-control service path, the system should not depend on it for the MVP.

## Approved Decisions

- Scope: platform skeleton plus the first `pdf_to_ppt` workflow.
- Web stack: Next.js Web/API container.
- Worker stack: Python Worker container for Gateway, tools, Runner Agent, Validator Agent, and Codex subprocesses.
- Queue: asynchronous queue-backed workflow dispatch, using Redis with a language-neutral job payload. The implementation can use Redis Streams, a database-backed queue, or a thin Node dispatcher if BullMQ is selected later.
- Database: PostgreSQL.
- Storage: local shared volume for MVP task inputs, intermediate artifacts, outputs, reports, and logs.
- Auth: simplest local account/password registration and login for MVP, with a boundary that can later be replaced by Auth.js, OAuth, or hosted auth.
- Agents: exactly one Runner Agent and one Validator Agent per active conversion task in the MVP.
- Validation: every page must be validated. Runner confidence is never enough to mark a page complete.
- AI usage: AI repairs Validator-identified problems. It does not perform slow full-page, from-scratch conversion for every page by default.

## Non-Goals For MVP

- Perfect reconstruction of every PDF feature.
- Guaranteed editable recreation of advanced charts, gradients, shadows, clipping masks, embedded fonts, complex vector art, or irregular tables.
- Multi-runner competition.
- Page-level Codex subprocess per page.
- Object storage or cloud storage.
- Billing, organization management, or production-grade identity management.
- Mandatory WPS, Adobe, or other paid third-party conversion service integration.

## Architecture

```text
Web/API Container
  Next.js Web UI
  API routes
  account/password auth
  PostgreSQL access
  queue producer
  task page and conversation UI

Worker Container
  Gateway
  PDF to PPT workflow
  Runner Agent Codex subprocess
  Validator Agent Codex subprocess
  fixed Python tools
  queue consumer
  shared task volume access
```

The Web/API container owns user interaction, task creation, uploads, task status, artifact browsing, and conversation history. It does not run conversion logic directly.

The Worker container owns workflow execution. Gateway reads queued jobs, loads the workflow definition, starts or resumes the appropriate agents, runs fixed tools, writes artifacts, and updates task events.

The containers share task files through a local volume:

```text
/shared/tasks/{task_id}/
  input.pdf
  extracted/
    pages.json
    objects/
    images/
    ocr/
  renders/
    pdf/
    ppt/
    diff/
  slides/
    slide-model.v1.json
    slide-model.v2.json
  output/
    candidate.v1.pptx
    candidate.v2.pptx
    final.pptx
  reports/
    validator.v1.json
    validator.v2.json
  prompts/
    runner.system.md
    validator.system.md
  logs/
```

## Workflow

```text
1. ingest
2. extract PDF objects and render page references
3. build initial slide model
4. generate candidate PPTX
5. validate every page
6. repair failed or uncertain pages and regions
7. repeat until pass, retry limit, manual review, or failure
```

The first generated PPTX should come from deterministic extraction and generation where possible. AI is used to organize, repair, and improve the intermediate slide model, especially when PDF objects are fragmented, missing, flattened, scanned, or visually wrong.

## Runner Agent

The Runner Agent is a Codex subprocess scoped to one task. It is responsible for rebuilding and repairing the PPTX candidate through tools and intermediate data, not for self-certifying quality.

Runner responsibilities:

- Read task instructions, user feedback, extraction reports, OCR output, slide models, previous Validator reports, and relevant page renders.
- Decide how raw PDF objects should be grouped into editable slide elements.
- Produce and revise the slide model JSON.
- Call deterministic tools to generate PPTX from the slide model.
- Call OCR or vision tools only for pages or regions that need them.
- Apply Validator feedback to specific slides, regions, or element definitions.
- Keep changes explainable through task events and logs.

Runner must not:

- Mark the task as successful.
- Hide raster fallback.
- Replace an entire slide with a full-page screenshot as the final solution.
- Re-run expensive AI analysis across all pages when Validator has isolated a smaller problem.

## Validator Agent

The Validator Agent is a Codex subprocess scoped to one task. It is responsible for independent quality evaluation and actionable feedback.

Validator responsibilities:

- Render every PDF page as the reference.
- Render every PPTX slide as the candidate.
- Compare every page visually.
- Inspect PPTX internals for editability.
- Compare reference text against editable PPTX text.
- Detect full-page screenshot slides and excessive raster fallback.
- Produce structured reports with per-page status, scores, issue regions, and suggested repair actions.
- Decide whether the task should continue repair, wait for user review, fail, or succeed.

Validator must not:

- Trust Runner confidence.
- Skip pages.
- Accept a visually close but mostly non-editable slide.
- Return only a vague pass/fail message.

## Agent Prompt And Skill Development

Runner and Validator prompt/skill development is a core part of the project, not a configuration afterthought. The implementation plan must include iterative prompt engineering, tool protocol design, regression samples, and conversion-quality debugging.

Runner prompt must teach the agent to:

- Operate on the task directory and never invent missing artifacts.
- Prefer editable PowerPoint primitives over raster fallback.
- Treat full-page screenshots as invalid output.
- Use deterministic tools before AI-heavy repair.
- Read Validator reports as the source of truth for repair priorities.
- Modify the slide model rather than manually editing generated PPTX whenever possible.
- Keep repairs scoped to failed pages or regions unless a global fix is required.

Validator prompt must teach the agent to:

- Evaluate every page independently and consistently.
- Separate visual fidelity, editability, and text coverage.
- Produce repair instructions precise enough for Runner to act on.
- Escalate to `manual_review` when a page cannot be confidently fixed.
- Reject output that passes visual checks by using full-page raster images.
- Preserve evidence: metrics, screenshots, diff images, PPTX structure findings, and issue regions.

Agent skills should include local instructions for:

- Reading task manifests and artifacts.
- Calling the PDF extraction tools.
- Calling PPTX generation tools.
- Calling render and diff tools.
- Interpreting Validator report schemas.
- Updating slide model JSON safely.
- Writing concise task events for the Web UI.

## Editable Reconstruction Strategy

The main conversion strategy is hybrid reconstruction:

```text
PDF object extraction
  -> normalized page object model
  -> initial editable slide model
  -> PPTX generation
  -> full-page validation
  -> AI-guided repair of failed regions
```

PDF internals are used first when available: text runs, embedded images, vector paths, fonts, coordinates, fills, strokes, page size, and z-order. OCR and vision models are fallback tools for scanned, flattened, or ambiguous regions.

The intermediate slide model is the main repair surface:

```json
{
  "slides": [
    {
      "page_number": 1,
      "size": { "width": 13.333, "height": 7.5 },
      "elements": [
        {
          "id": "s1-title",
          "type": "text",
          "text": "Quarterly Report",
          "x": 0.8,
          "y": 0.5,
          "w": 5.2,
          "h": 0.6,
          "font": "Arial",
          "size": 28,
          "color": "#111111"
        }
      ],
      "raster_fallback_regions": []
    }
  ]
}
```

The slide model should remain deterministic, versioned, and diffable so Runner repairs can be reviewed and reproduced.

## Validation Strategy

Every page receives independent validation. The Validator report is the only source of truth for completion.

Per-page metrics:

- `visual_score`: similarity between PDF render and PPT render.
- `editable_score`: whether visible content is represented by editable PPTX elements.
- `text_coverage_score`: whether reference text appears as editable PPTX text.
- `raster_fallback_ratio`: how much of the slide is represented by raster regions.
- `issues`: structured visual, text, editability, and tool errors.

Hard failures:

- A slide is mostly one full-page image.
- Important visible text is missing from editable PPTX text.
- A page was not rendered or validated.
- PPTX cannot be opened or rendered.
- Validator cannot produce evidence for a pass decision.

Repair statuses:

```text
pass
repair_needed
manual_review
failed
```

The Validator may allow small bounded raster fallback regions, but must report them. For example, a complex decorative background may be rasterized while labels and surrounding text remain editable. A full-page screenshot is not acceptable.

## Data Model

```text
User
  id
  email
  password_hash
  created_at

WorkflowTask
  id
  user_id
  workflow_type
  status
  input_file_path
  output_file_path
  current_attempt
  max_attempts
  created_at
  updated_at

TaskArtifact
  id
  task_id
  artifact_type
  path
  metadata
  created_at

TaskEvent
  id
  task_id
  role
  event_type
  message
  payload
  created_at

TaskConversationMessage
  id
  task_id
  role
  content
  created_at
```

`TaskEvent` records machine events such as extraction completion, candidate generation, validation scores, and repair attempts. `TaskConversationMessage` records user and AI conversation on the task page.

## Task State Machine

```text
queued
running_extract
running_initial_build
running_validate
running_repair
waiting_user_review
succeeded
failed
cancelled
```

`succeeded` requires all pages to pass Validator thresholds. `waiting_user_review` means a usable candidate and report exist, but the system needs user review or has exhausted repair attempts. `failed` means no usable output can be produced.

## User Conversation Loop

The task page supports follow-up requests on the same task:

```text
User message
  -> save TaskConversationMessage
  -> enqueue repair job
  -> Gateway loads task artifacts and conversation
  -> Runner revises slide model
  -> generator produces new PPTX
  -> Validator rechecks every page
  -> Web displays new version and report
```

User feedback becomes additional repair context for Runner, but Validator still decides quality after regeneration.

## Tooling Boundaries

Fixed tools should be implemented as deterministic commands with structured inputs and outputs:

- PDF object extractor.
- PDF renderer.
- OCR/VLM region analyzer.
- Slide model builder.
- PPTX generator.
- PPTX renderer.
- Visual diff tool.
- PPTX structure inspector.
- Text coverage checker.

Agents call these tools through a narrow protocol. Tool failures should be captured as task events and Validator issues when relevant.

## WPS And External Providers

The architecture may include a `ConversionProvider` interface, but WPS is not a required dependency for MVP.

Provider categories:

- `local_hybrid_reconstruction`: primary MVP path.
- `wps_like_provider`: optional future provider if cost, licensing, privacy, and automation are acceptable.
- `external_api_provider`: optional future provider with explicit user consent and artifact auditing.

Any provider output must still pass Validator. A provider that returns a mostly raster PPTX fails the editability checks.

## Quality Iteration Plan

Conversion quality will improve through a sample-driven loop:

1. Collect representative PDFs.
2. Run the workflow and persist every artifact.
3. Review Validator reports and user feedback.
4. Update tools, prompts, skills, and thresholds.
5. Re-run regression samples.
6. Track visual, editability, text coverage, and runtime metrics over time.

The prompt/skill work for Runner and Validator should be versioned alongside code so regressions can be traced to a tool, prompt, threshold, or model change.

## Risks

- Editable reconstruction is substantially harder than screenshot-based conversion.
- PPTX cannot express every PDF visual feature exactly.
- Font availability can change text wrapping and visual fidelity.
- Rendering PPTX reliably in a container may require LibreOffice or another renderer and careful environment setup.
- OCR/VLM output can introduce text errors, especially for numbers and tables.
- Validation thresholds need real samples; they should start conservative and become data-driven.

## References

- WPS PDF to PPT product page: https://pdf.wps.com/convert-pdf-to-ppt/
- Adobe Acrobat PDF to PowerPoint product page: https://www.adobe.com/acrobat/how-to/pdf-to-powerpoint-pptx-converter.html
- LibreOffice import/export limitations: https://help.libreoffice.org/latest/ta/text/shared/guide/ms_import_export_limitations.html
- PyMuPDF documentation: https://pymupdf.readthedocs.io/
- python-pptx documentation: https://python-pptx.readthedocs.io/
