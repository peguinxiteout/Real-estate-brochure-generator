# Changelog

Newest entry first.

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
