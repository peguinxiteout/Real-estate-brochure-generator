# Changelog

Newest entry first.

## 2026-11-01: Brief agent on Groq

The Brief step now uses an LLM to fill empty form fields with facts the prompt states. The other agents are still stubs.

- `src/brochure/llm/openai_compatible.py`: `OpenAICompatibleClient` (the `openai` SDK on any OpenAI-compatible base URL) and `client_from_env()`, which reads `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (defaults: Groq and `openai/gpt-oss-120b`). Temperature 0. Strict `json_schema` on the models Groq documents as supporting it, JSON-object mode with the schema in the system message on any other. HTTP 429 is retried up to 3 attempts honouring `Retry-After`, then `LLMRateLimited`; other failures are `LLMError`; a reply that is not a JSON object is `LLMBadReply`. The key never appears in an error, a log or a repr. `images=` raises `NotImplementedError`.
- `src/brochure/agents/brief.py` and `prompts/brief_extract.md`: `brief_agent(brief, llm) -> BriefForm`. One `brief.extract` call; the merge and the grounding check are in code. The form wins; every string and number the model fills must appear in the prompt; `rera_number` must appear verbatim; a bad reply is retried once; any failure returns the form unchanged and logs a warning.
- `pipeline.real_agents(llm)`: the real Brief agent and the stubs for every other step.
- Graph change (not a contract change): the brief node now keeps the form a brief step returns (`BriefOutcome.form`, default `None`). Without it the question loop ran on the original form and kept asking for fields the Brief agent had already filled. Stub runs are unchanged.
- `sample/brief_sparse.json`; the live test `tests/llm/test_brief_live.py` (marker `llm`, skips without `LLM_API_KEY`).
- CI now runs `-m "not integration and not llm"`.
- `.env` is git-ignored; `.env.example` lists the three variable names. Dependency: `openai==3.42.0`.

## 2026-10-30: Pipeline on stub agents

The whole flow (brief, copy, layout, render, QA loop, human review, export) runs end to end on the Aurelia Heights sample with no LLM and no rendering. Real agents will replace the stubs one at a time without changes to the graph.

- `src/brochure/pipeline/`: `build_graph(agents, checkpointer, llm)` compiles a LangGraph graph over `PipelineState`. `Agents` holds one callable per step; the graph imports no concrete agent.
- Brief and vision run in parallel and join before the copywriter. Missing required fields pause the run (`ask_user`, with `missing_fields` set); resuming with `{field: value}` re-runs the brief step. An answer that does not validate (unknown field, wrong type, blank or still invalid value, not an object) is never raised: the valid part is kept and the question is asked again with the fields still missing and a short message per bad field. The review question is asked again the same way. Both questions always carry the same keys (`errors` / `error`). The brief step itself is real code (form to `ProjectFacts`), not a stub.
- QA routing by `route_to`: `copywriter` loops back to the copywriter, `layout` to layout, `none` does not loop. At most 3 QA rounds; issues left at the end go to `spec.qa_warnings`. `human_review` pauses and resumes with `approved` (export, then end) or `changes_requested` (layout, render, QA, review again; `qa_round` restarts at 0).
- Stub agents (`pipeline/stubs.py`): vision, copywriter, layout (every slot of `classic-8pp` filled once), renderer (fake paths, no files), a scripted QA, and a no-op export. No stub calls the LLM.
- Checkpointers: in-memory for tests, SQLite for real runs; both use a serializer that lists the contract models.
- `sample/image_tags.json` (moved from `tests/fixtures/`) and the new `sample/stub_copy.json` feed the stubs.
- Dependencies: `langgraph==1.2.18` and `langgraph-checkpoint-sqlite==3.1.2`.
- Not done: image tools are not in the graph; no field for the text of a chat edit in `PipelineState`.

## 2026-10-30: README

- Added `README.md`: what the project is, what is built and what is not, the planned pipeline, repository layout, getting started, the contracts, print rules, templates and slots, the LLM interface, the sample project, working rules, a glossary and known limitations.
- `CONTRIBUTING.md`: docs-only changes may go straight to `master` after the tests pass; code changes still go on a `feature/` or `fix/` branch.

## 2026-10-30: CI

- GitHub Actions workflow `.github/workflows/tests.yml`: job `tests` on ubuntu-latest, Python 3.12, pip cache. It installs with `pip install -e ".[dev]"` and runs `python -m pytest -m "not integration"`.
- Runs on every push to `feature/**` and `fix/**` and on every pull request into `master`. A newer run on the same ref cancels the older one. Permissions are `contents: read`; no secrets.
- Integration tests (WeasyPrint, Ghostscript) are excluded for now; the runner does not install Ghostscript or extra Pango packages.

## 2026-10-30: Contracts (Week 0)

Shared contracts, so a second developer can build against them without waiting for the agents. No agents, graph or rendering yet.

- **Print config and DPI maths** (`src/brochure/print_config.py`, `src/brochure/dpi.py`)
  - DPI rule: pass at 300 or more, warn from 250 up to (not including) 300, fail below 250. Thresholds live in the config only.
  - Effective DPI = `min(img_w_px / slot_w_in, img_h_px / slot_h_in)`, with the slot size including 3 mm of bleed for each edge in the slot's `bleed_edges`.
  - `min_px = ceil(slot size in inches, bleed included, x 300)`, computed with exact decimal maths. The slots loader computes it; it is never stored in `slots.json`.
- **Pydantic contracts** (`src/brochure/contracts/`): BrandKit, ProjectFacts, BriefForm, Brief, ImageTag, QAIssue, BrochureSpec, SlotsFile/Slot, ImageManifest and PipelineState. All use `extra="forbid"`, so a typo in JSON fails loudly.
  - Brief is `{form: BriefForm, prompt}`. BriefForm is ProjectFacts with every field optional.
  - PipelineState carries the Brief, `project_facts` and `missing_fields` (set by the Brief agent), render outputs (`pdf_path`, `page_images`) and the QA loop state.
  - `QAIssue.route_to` is required.
- **JSON Schema export** to `contracts/json/` via `python tools/export_schemas.py`. A drift test compares parsed JSON, so a CRLF checkout cannot fail it, and its failure message names the regenerate command.
- **Template** `templates/classic-8pp/slots.json`: 8 pages A4 portrait, 33 slots, no pricing. The back cover has the RERA number and a 25x25 mm QR slot, marked provisional because compliance has not given a minimum QR size.
- **LLM interface** (`src/brochure/llm/`): `LLMClient` protocol, `FakeLLM` (canned responses by task, records every call, names the missing task in its error) and the `Agent[I, O]` typing protocol. The `llm` pytest marker is registered. No real client.
- **Sample project** "Aurelia Heights" in `sample/`, with `tools/make_sample_images.py` (deterministic Pillow JPEGs into `sample/images/`) and `tests/fixtures/image_tags.json`. For their intended slots, 3 of the 12 images fail DPI and 1 warns.
- **Repo hygiene**: `CONTRIBUTING.md` and `.gitattributes` (LF in the repo; jpg, png, pdf and ttf are binary).

Known follow-ups:
- Logo slots need a vector/SVG DPI exemption.
- Non-hero slot sizes are placeholders.
- PipelineState has no chat-edit field yet.
