# Real estate brochure generator

## 1. What this is

An agentic system that turns a project brief, a prompt and a folder of photos into a print-ready brochure PDF for a
real estate company in India. Agents fill pre-built HTML/CSS templates; they do not design pages from scratch. A human
reviews and approves the result before it is exported.

Scope of v1, as far as the repo defines it today:

- One template, `classic-8pp`: 8 pages, A4 portrait, 3 mm bleed, 300 DPI target.
- No pricing page. Pricing is left out of the template on purpose.
- A4 is the only page size in the print config.

Most of the system is not built yet. Section 2 says what exists and what does not.

## 2. Status

Built (see [docs/CHANGELOG.md](docs/CHANGELOG.md) for the history):

- Contracts: Pydantic models for everything the pipeline passes around, plus exported JSON Schemas (section 6).
- Print rules: print config and DPI maths (section 7).
- Print geometry: page boxes (trim, 3 mm bleed, 10 mm slug), crop marks, the page count rule, and a blank proof PDF with those boxes and marks, made with WeasyPrint (section 7, "Print geometry"). The renderer uses the same page rule, marks and BleedBox finisher.
- The `classic-8pp` HTML/CSS template and a real renderer: BrochureSpec + brand kit + image tags to an 8-page print PDF and one PNG per page (section 8, "Template and renderer"). `tools/render_sample.py` renders the sample through the graph.
- Bundled brand fonts: Inter (headings) and Open Sans (body), static TTFs with their OFL licences (section 8, "Fonts").
- Slots format, loader and the `classic-8pp` template (section 8).
- LLM interface with a `FakeLLM` for tests, and a real client for any OpenAI-compatible endpoint (Groq by default) (section 9).
- The Brief and Copywriter agents are real, using the LLM (section 3): Brief fills empty form fields with facts the prompt states; Copywriter writes the free-text slots, checked in code.
- The Layout step's image assignment is real, in code with no LLM (section 3): images go to slots by kind, resolution against the DPI rule, subject and shape, and every problem is a warning for the reviewer. The other steps are still stubs.
- The pipeline graph (LangGraph), with pause and resume for missing fields and for human review (section 3). `stub_agents()` runs it with no LLM; `real_agents()` swaps in the real Brief and Copywriter agents, which use the client that `build_graph` is given, and the rule-based layout.
- A fictional sample project, "Aurelia Heights" (section 10).
- `brochure doctor`: checks Python, WeasyPrint, Ghostscript and the bundled font files. It is the only CLI command, and in WSL every check passes.
- CI on GitHub Actions: runs the unit tests on pushes to `feature/**` and `fix/**` and on pull requests into `master`.

Not built:

- Real agents other than Brief and Copywriter. Vision and the QA critic are stubs; Layout does not yet choose between page layouts or apply chat edits.
- The image tools. They are not in the graph yet.
- CMYK conversion. The PDF is RGB; the Ghostscript CMYK step comes later.
- Export. The stub does nothing.
- An API and a frontend.

## 3. How it will work

This is the design the contracts were written for. The graph that connects the steps is built and runs on stub agents (see "The graph on stub agents" below). Vision, the image tools, the QA critic and export are not built, and step 3 is not in the graph yet.

```mermaid
flowchart TD
    IN["Inputs: brand kit, brief form + prompt, photos"] --> S1["Step 1: Brief agent"]
    S1 -->|"required field missing: ask the user"| S1
    IN --> S2["Step 2: Vision agent"]
    S2 --> S3["Step 3: Image tools"]
    S1 --> S4["Step 4: Copywriter"]
    S3 --> S5["Step 5: Layout agent"]
    S4 --> S5
    S5 --> S6["Step 6: Renderer"]
    S6 --> S7["Step 7: QA critic"]
    S7 -->|"issues, at most 3 rounds"| S4
    S7 -->|"issues, at most 3 rounds"| S5
    S7 -->|"no errors"| S8["Step 8: Human review"]
    S8 -->|"chat edits"| S5
    S8 -->|"approved"| S9["Step 9: Export"]
```

| Step | What it does | Today |
|---|---|---|
| 1. Brief agent | Turns the form and the prompt into `ProjectFacts`. Lists required fields that are missing in `missing_fields` so the user can be asked. | Real. `real_agents()` runs the Brief agent (one LLM call) before the form-to-facts conversion and the question loop (bad answers are asked again). `stub_agents()` skips the LLM and uses the form only. |
| 2. Vision agent | Runs in parallel with step 1. Describes each photo as an `ImageTag` (kind, subject, quality, focal point). | Stub: returns the 12 sample image tags. |
| 3. Image tools | Plain code, not an agent. For each image: crops it to its slot's aspect ratio around the focal point, fixes exposure, runs the DPI check, and upscales by at most 2x. Low-resolution images are flagged and limited to small slots. Planned, not built. | Not built, not in the graph. |
| 4. Copywriter | Writes the text for each text slot, within its `char_budget`. | Real. `real_agents()` runs the Copywriter agent (one LLM call, a second only for slots that fail a check) for the 7 free-text slots; code fills the other 11 text slots word for word. `stub_agents()` uses sample text. |
| 5. Layout agent | Chooses which image and text goes in which slot and produces the `BrochureSpec`. Also applies the human's chat edits. | Image assignment is real: `real_agents()` places images by rules in code (no LLM) and warns about every problem. `stub_agents()` uses the manifest's intended slots. Chat edits are not applied yet. |
| 6. Renderer | Fills the HTML/CSS template from the spec and produces the PDF and one PNG per page. | Real in `real_agents()`: WeasyPrint and Ghostscript, into `out/<thread id>/` (section 8). `stub_agents()` keeps the stub (fake paths, no files), so CI needs no Pango. |
| 7. QA critic | Looks at the pages and the spec and returns `QAIssue`s. Each issue says who should fix it (`route_to`). The loop stops after 3 rounds. | Stub: no issues unless scripted. The routing and the 3-round limit are real. |
| 8. Human review | A person approves, or asks for changes in chat. | Real: pauses, resumes with `approved` or `changes_requested`. No chat text yet. |
| 9. Export | Writes the approved PDF. | Stub: does nothing. |

### The graph on stub agents

`src/brochure/pipeline/` holds the graph, built with LangGraph. `build_graph(agents, checkpointer, llm)` compiles it
over `PipelineState`. `agents` is an `Agents` dataclass with one callable per step; the graph never imports a concrete
agent, so a real agent replaces a stub by being passed in, with no change to the graph. Every agent has the shape
`(state, llm) -> output`. The stubs are in `pipeline/stubs.py`. They read `templates/classic-8pp/slots.json` and the
files in `sample/` (including `sample/stub_copy.json`), make no LLM calls and render nothing.

- Brief and vision start in parallel; the copywriter starts when both are done. If the brief has missing required
  fields, the run pauses at `ask_user` with `missing_fields` set. The caller resumes with the values, for example
  `Command(resume={"rera_number": "..."})`. Each answered field that is valid is kept; a field that is not (unknown,
  wrong type, blank, or still failing `ProjectFacts`) is refused and the question is asked again. Nothing raises. The
  brief step runs again when nothing is missing.
- After the renderer, the QA step runs. It sees the renderer's own issues (text overflow) as well as its own. An issue routed to `copywriter` sends the run back to the copywriter (then
  layout, render, QA); one routed to `layout` goes back to layout; one routed to `none` does not loop. After 3 QA
  passes the run moves on whatever the issues say. Issues that do not loop, and any left after the 3rd pass, are
  added to `spec.qa_warnings`, after the layout's own warnings.
- `human_review` pauses. The caller resumes with `"approved"` (the run goes to export and ends) or
  `"changes_requested"` (back through layout, render and QA to review; `qa_round` restarts at 0). Any other answer is
  asked again.
- What the caller sees when the run pauses (`graph.get_state(config).tasks[0].interrupts[0].value`):

  ```
  missing fields:  {"ask": "brief", "missing_fields": ["rera_number"], "errors": {}}
  after a bad one: {"ask": "brief", "missing_fields": ["rera_number"], "errors": {"rera_number": "must not be empty"}}
  review:          {"ask": "review", "pdf_path": "...", "page_images": ["...", ...], "error": null}
  after a bad one: {"ask": "review", "pdf_path": "...", "page_images": [...], "error": "answer 'approved' or 'changes_requested', not 'maybe'"}
  ```

  `errors` maps a field name to a short message; an unknown field is keyed by the name it was sent under (message
  "unknown field"), and an answer that is not an object is keyed "answer". `missing_fields` lists what is still
  missing after the valid part of the last answer was applied. If nothing is missing but an error was reported,
  resume with `{}` to carry on.
- Checkpointers are passed in: `memory_checkpointer()` for tests, `sqlite_checkpointer(path)` for runs that must
  survive a restart.

This was run from the repo root:

```python
import json

from langgraph.types import Command

from brochure.contracts.brand import BrandKit
from brochure.contracts.project import Brief
from brochure.contracts.state import PipelineState
from brochure.llm import FakeLLM
from brochure.pipeline import build_graph, memory_checkpointer, stub_agents

state = PipelineState(
    template_id="classic-8pp",
    brand_kit=BrandKit.model_validate(json.load(open("sample/brand_kit.json"))),
    brief=Brief.model_validate(json.load(open("sample/brief.json"))),
    image_dir="sample/images",
)
graph = build_graph(stub_agents(), memory_checkpointer(), FakeLLM({}))
config = {"configurable": {"thread_id": "demo"}}

graph.invoke(state, config)
print(graph.get_state(config).next)  # paused at the review step
graph.invoke(Command(resume="approved"), config)
print(graph.get_state(config).next)  # empty: the run has finished
```

```
('human_review',)
()
```

### The Brief agent

`src/brochure/agents/brief.py`. `brief_agent(brief, llm) -> BriefForm` makes one `brief.extract` call with the form
(empty fields included) and the prompt. The prompt text is in `src/brochure/agents/prompts/brief_extract.md`. The merge
is done in code, not by the model:

- **Form wins.** The model may only fill fields that are empty in the form (null, blank, or an empty list; a list is
  filled whole or not at all).
- **Grounding.** Every string it fills must appear in the prompt (ignoring case and spacing) and every number it fills
  must appear in the prompt as a number (`1,090` counts as 1090). `rera_number` must appear in the prompt character for
  character. A value that fails is dropped (and logged at INFO); in a list, only that item is dropped. This includes
  `tone_notes`, so the model is told to copy the user's words for it. Numbers written as words ("two") are not found.
- **Fallback.** A reply that fails validation is retried once with the validation error in the message. If it fails
  again, or the client raises `LLMRateLimited` / `LLMError`, the form is returned unchanged and a warning is logged.
  The missing-fields question then asks the user, exactly as with the stubs. The run never crashes on an LLM failure.

The brief node saves the form the Brief agent returns into the run (`BriefOutcome.form`), so the question loop works
on the merged form. Because the brief step runs again after the user answers, a run that asks a question makes two
`brief.extract` calls.

### The Copywriter agent

`src/brochure/agents/copywriter.py`. `copywriter_agent(inputs, llm) -> dict[slot_id, str]` makes one `copy.write` call.
The prompt is `src/brochure/agents/prompts/copy_write.md`; the reply schema is strict, with one required string
property per owned slot (it says nothing about length; the code checks that). The model is sent only: the
`ProjectFacts` (without the tone), the company name, each image's `kind`, `subject` and `features` (no paths), the tone notes,
the owned slots (`id`, `page`, `char_budget`, `max_words`, `comment`) and, when the QA loop sent the run back, the QA issues routed to
the copywriter. Facts are strict, wording is free.

**Which slots it writes.** Text slots of `classic-8pp` are split in two. Code fills the verbatim slots word for word
(`src/brochure/verbatim.py`); the Copywriter never sees or rewrites them, so legal and contact text is never reworded.

| Written by the Copywriter (char budget) | Filled by code from the facts and the brand kit (char budget) |
|---|---|
| `cover_tagline` (90, 12 words), `overview_headline` (60, 8), `overview_intro` (600, 85), `overview_highlights` (240, 34), `amenities_blurb` (250, 35), `plan_note` (160, 22), `about_headline` (60, 8) | `cover_title` (40; the project name), `cover_rera_line` (60), `rera_number` (60), `location_address` (120), `location_landmarks` (400), `amenities_list` (300), `config_table` (400), `specs_list` (700), `about_text` (450), `contact_block` (200), `disclaimer` (500) |

The pipeline step (`pipeline/real.py`) returns the verbatim slots plus whatever the Copywriter wrote as `slot_copy`.

**Checks, per slot, in code** (`src/brochure/agents/copy_checks.py`). Each failure gives a short reason:

- Budget: not empty, and `len(text) <= char_budget`. A model cannot count characters, so each slot is also sent a
  `max_words` (the char budget divided by `CHARS_PER_WORD = 7`, rounded down, in `copy_checks.py`), and the reason for
  a long text names a length to aim for (85% of the budget).
- Numbers: every number (digits, `1,090`, decimals, and number words from one to twenty) must equal a number found
  anywhere in the `ProjectFacts`, including inside strings such as "2 BHK" or "Dec 2028". A thousands group split by a
  non-breaking space counts as one number.
- Names: every capitalised word that does not start a sentence or a line must appear (any case) in the facts, in the
  brand kit's `company_name`, or in the allow-list. This also rejects headlines in Title Case.
- Text is normalised first, in the checks and in the returned copy: any Unicode space separator (U+202F, U+00A0,
  U+2009, ...) becomes a plain space, and U+2010 and U+2011 become `-`. Curly quotes and apostrophes are kept.
- Money: currency symbols and words (`copy_money_words.txt`), as whole words.
- Superlatives, promises and location clichés ("prime location", "minutes from", "walking distance", "stone's throw"):
  `copy_banned_phrases.txt`, as whole words or phrases ("bestow" is fine).

The three lists are data files in `src/brochure/agents/data/` (`copy_name_allowlist.txt`, `copy_money_words.txt`,
`copy_banned_phrases.txt`): one entry per line, `#` comments, shipped with the package.

**Retry and fallback.** If any slot fails, the model is asked once more with only the failing slots. A slot that fails
only on length is *edited*, not rewritten: the retry sends its previous text (`shorten`) and asks for it shortened by
cutting words or sentences. Any other failure (a number, a name, money, a banned phrase, an empty text) is written again
with its reasons (`problems`). Slots that passed keep their first text whatever the second reply says.

**Trim.** A slot still failing after the retry is trimmed in code: the longest run of whole sentences (or whole lines)
from the start that fits the budget and passes every check is kept, and an info line says so. Nothing is cut inside a
sentence ("sq. ft." does not end one). Headlines, taglines and titles (ids ending `_headline`, `_tagline`, `_title`) are
never trimmed. If nothing fits, the slot is left out of the result and one warning lists it with its reasons.

**Bad replies and client errors.** A reply that is not valid JSON (`LLMBadReply`) is asked for once more with the error, as the Brief agent does; a second
one falls back like any other client error. A client error (`LLMRateLimited`, `LLMError`, or that second bad reply)
stops the asking, keeps what already passed and logs one warning with the cause. The run never crashes on the model.

**Wording rules that only the prompt enforces.** Only a render is an "artist's impression"; a photo is a photograph and a
floor plan or a map is never called one. Each `overview_highlights` line states a fact from the project (a
configuration, the location, the possession date, an amenity or a landmark), not a picture. `overview_intro` is a short
summary that does not list every landmark, configuration or specification. No code check looks for
either, so the live test reads the copy (it asserts only that `plan_note` does not say "artist").

**Missing copy.** The layout stub puts the visible text `[copy needed: <slot_id>]` in any text slot with no copy, so the
reviewer sees the gap (the QA critic will later flag these placeholders).

**What the checks cannot see.** Numbers, names, money and superlatives are checked in code. A made-up description with
none of those ("a gym with floor-to-ceiling windows") passes; the prompt forbids it, and only a later reviewer or QA
critic can catch it. The brief's free-text prompt is not sent to the Copywriter.

### The Layout step: image assignment in code

`src/brochure/layout.py`, with the rules in `templates/classic-8pp/layout_rules.json`. No LLM: the same tags give the
same assignment every time. `real_agents()` uses it; `stub_agents()` still puts each image in the manifest's
`intended_slot`. Text, the verbatim slots, both logos (from the brand kit) and the QR code are filled as before.

**Rules file.** One rule per non-logo image slot: the image `kinds` it accepts (`photo`, `render`, `floor_plan`, `map`),
preferred `keywords`, and a `priority` (the order in which slots pick: the cover hero first, then large slots, then
small). It belongs to the layout, not to the shared contracts. `rule_problems()` checks it against the template: every
non-logo image slot has exactly one rule, every rule names such a slot, no two rules share a priority.

**Eligible.** An image can go in a slot when the slot accepts its kind and its effective DPI there (the slot size with
its bleed, the same rule as everywhere) is not in the fail band. The warn band is allowed.

**Score** (higher wins; weights in `ScoreWeights`, one place):

| Term | Weight |
|---|---|
| Each of the slot's keywords found in the image's subject or features (any case) | +100 |
| Effective DPI in the pass band (warn band: 0) | +20 |
| Shape: subtracted per unit of \|ln(image ratio / slot ratio)\| (less cropping is better) | -10 |
| Quality grade: good / fair / poor | +6 / +3 / 0 |

The weights are ordered so that what the image shows comes first, then print quality, then cropping, then the grade.

**Picking.** Slots pick in priority order; each takes its best-scoring eligible image that is not used yet, so an image
is used at most once. Ties go to the image whose path sorts first, so the input order never matters.

**Warnings.** Every problem becomes a `QAIssue` in `spec.qa_warnings` with `route_to` `none` (no agent can fix it; the
user must supply a better image). An unfilled slot is an `error`; the other two are `warning`s:

- `layout.slot_unfilled` (severity `error`), on the slot's page: no image of its kind, every image of its kind that fits is used
  elsewhere, or the images of its kind were too small (each named with its DPI, rounded down). The slot is left out of
  its page's slots; `PageSpec.slots` is a plain dict, so the contract allows it. No placeholder image is written.
- `layout.dpi_warn` (severity `warning`), on the slot's page: an image placed in the warn band, with its effective DPI.
- `layout.image_unused` (severity `warning`), no page: an image used nowhere, and why (no slot accepts its kind, too small for every slot
  that does, or every slot it fits took a better image).

QA issues that go to the reviewer are added after these. A QA issue routed to `layout`, and `changes_requested`, re-run
the same layout: nothing acts on the instruction yet (chat edits come later).

On the sample, the 9 images that can be placed land in their intended slots; `plan_img_b`, `amenity_img_c` and
`about_img` are left unfilled because their images fail the DPI rule, and `amenity_clubhouse.jpg` is placed with a
warning (section 10).

Run the pipeline tests. They use the in-memory checkpointer and a temporary SQLite file, and they fail if anything
opens a network connection or calls the `FakeLLM`:

```
~/.venvs/brochure/bin/python -m pytest tests/unit/test_pipeline_graph.py tests/unit/test_pipeline_stubs.py tests/unit/test_pipeline_brief.py
```

## 4. Repository layout

```
.github/workflows/tests.yml   CI: unit tests on branch pushes and pull requests
contracts/json/               JSON Schema for each exported model (generated, committed)
docs/CHANGELOG.md             history, newest entry first
sample/                       fictional "Aurelia Heights" project (brand kit, brief, image manifest, image tags, logo)
src/brochure/
  cli.py                      `brochure` command (only `doctor`)
  doctor.py                   environment checks and fix hints
  print_config.py             A4 size, bleed, slug, crop marks, page count multiple, DPI thresholds
  dpi.py                      min_pixels, effective_dpi, classify_dpi
  fonts.py                    the bundled font faces (family, weight, style, file) and the missing-file check
  render/                     geometry.py (page boxes, crop marks, page count, no WeasyPrint); positions.py (slot
                              positions and their rules); html.py (spec to HTML, focal-point crop, overflow check);
                              qr.py (vector QR); pdf.py (brochure PDF and page PNGs, blank proof PDF)
  slots.py                    load slots.json, compute min_px
  layout.py                   layout rules, image eligibility and scoring, image assignment and its warnings
  contracts/                  Pydantic models and the schema export
  llm/                        LLMClient, FakeLLM, OpenAICompatibleClient, Agent protocol
  verbatim.py                 the text slots code fills word for word (RERA, contact, lists, about text, disclaimer)
  agents/                     real agents (Brief, Copywriter), their prompt files, the copy checks and their data files
  pipeline/                   LangGraph graph, stub agents, real_agents, checkpointers
assets/fonts/                 Inter/ and OpenSans/: static TTFs and each family's OFL.txt
templates/classic-8pp/        slots.json, layout_rules.json, positions.json, brochure.html.j2, brochure.css
sample/pages/                 the sample's 8 page PNGs at 100 DPI, for QA critic work (committed)
out/                          renderer output (git-ignored)
tests/unit/                   fast tests, no network
tests/integration/            tests that need WeasyPrint or Ghostscript
tests/llm/                    tests that call the real model (marker `llm`, skipped without a key)
tools/                        export_schemas.py, make_sample_images.py, make_blank_pdf.py, render_sample.py
README.md                     this file
CONTRIBUTING.md               setup, TDD rules, branching rules
pyproject.toml                dependencies, pytest markers
```

## 5. Getting started

Setup is done in WSL (Ubuntu). The steps are in [CONTRIBUTING.md](CONTRIBUTING.md#setup-wsl-ubuntu). The examples below
use the virtualenv from that page, `~/.venvs/brochure`, and are run from the repo root.

Check the environment:

```
~/.venvs/brochure/bin/brochure doctor
```

The doctor prints one line per check and exits with 1 if any check fails. In WSL all four pass. The fonts check looks
for each bundled font file and each family's `OFL.txt` under `assets/fonts` and names any that are missing.

Run the tests:

```
~/.venvs/brochure/bin/python -m pytest                       # everything
~/.venvs/brochure/bin/python -m pytest -m "not integration and not llm"  # what CI runs
~/.venvs/brochure/bin/python -m pytest -rs                   # also print the reason for every skip
```

With Ghostscript and Pango installed and no `LLM_API_KEY` set, expect every test to pass except the one live LLM
test, which skips with its reason. Without them, the integration tests skip with a stated reason too. A skip is never meant to look like a pass.

Generate the sample images (they are git-ignored):

```
~/.venvs/brochure/bin/python tools/make_sample_images.py
```

This writes the 12 JPEGs listed in `sample/images.json` to `sample/images/`. The output is the same on every run.

## 6. The contracts

The models are in `src/brochure/contracts/`. All of them reject unknown fields, so a typo in JSON is an error. Field
names are plain snake_case and stable.

| Model | What it is | Produced by / used by (as designed) |
|---|---|---|
| `BrandKit` | Company name, logo, colours (hex, optional CMYK), fonts, about text, contact, disclaimer. | Provided by the user. Used by Copywriter, Layout, Renderer. |
| `BriefForm` | The form the user fills in: `ProjectFacts` with every field optional. | User. Read by the Brief agent. |
| `Brief` | `{form: BriefForm, prompt: str}`. | User. Pipeline input. |
| `ProjectFacts` | Validated facts: name, RERA number (required, non-empty), location, configurations, amenities, specifications, landmarks, possession, tone notes. | Brief agent. Used by Copywriter, Layout, QA critic. |
| `ImageTag` | What one photo shows: kind, subject, size, quality, features, focal point (fractions 0..1). | Vision agent. Used by image tools and Layout. |
| `Slot` / `SlotsFile` | One box on a page, and the file that lists them (section 8). | Written by hand per template. Read by the loader, then Layout, QA, Renderer. |
| `BrochureSpec` | The filled brochure: template id, pages (layout id and the content of each slot), QA warnings, version. Page count must be a positive multiple of 4. | Layout agent. Used by Renderer, QA critic. |
| `QAIssue` | A finding: check, page, severity, note, and `route_to` (copywriter, layout or none; required). | QA critic. Used by Copywriter, Layout and the human reviewer. |
| `ImageManifest` | List of image files with pixel size, kind and intended slot. | Only the sample project uses it. |
| `PipelineState` | What the graph carries: inputs, `project_facts`, `missing_fields`, `image_tags`, `slot_copy`, `spec`, `pdf_path`, `page_images`, `qa_issues`, `qa_round`, `approval_status`. | Every step reads and writes parts of it. |

JSON Schemas for these models (except `BriefForm`, which is nested inside `Brief`) are in
[contracts/json/](contracts/json/). The frontend generates its types from them. After changing a model, regenerate
and commit them in the same branch:

```
~/.venvs/brochure/bin/python tools/export_schemas.py
```

A test fails, and names this command, if the committed files are out of date. It compares parsed JSON, so line
endings do not matter.

## 7. Print rules

Defined in `src/brochure/print_config.py` and used everywhere; do not repeat the numbers elsewhere.

- A4 portrait, 210 x 297 mm.
- Bleed: 3 mm on every edge listed in a slot's `bleed_edges`.
- Target resolution: 300 DPI.
- Effective DPI = `min(img_w_px / slot_w_in, img_h_px / slot_h_in)`, where the slot size includes the bleed.
- Pass at 300 DPI or more. Warn from 250 up to, not including, 300. Fail below 250.
- `min_px = ceil(slot size in inches, bleed included, x 300)`.

Worked example from the sample project. This script was run from the repo root and printed the two lines below it:

```python
import json
from brochure.dpi import classify_dpi, effective_dpi
from brochure.slots import load_slots

template = load_slots("templates/classic-8pp/slots.json")
manifest = json.load(open("sample/images.json"))["images"]

for entry in manifest:
    if entry["filename"] in ("hero_tower.jpg", "amenity_clubhouse.jpg"):
        slot = template.get(entry["intended_slot"])
        dpi = effective_dpi(entry["width_px"], entry["height_px"], slot.bleed_width_mm, slot.bleed_height_mm)
        print(entry["filename"], f'{entry["width_px"]}x{entry["height_px"]} px',
              "->", slot.id, f"{slot.bleed_width_mm:g}x{slot.bleed_height_mm:g} mm",
              "min_px", slot.min_px, f"{dpi:.1f} DPI", classify_dpi(dpi).value)
```

```
hero_tower.jpg 2600x3650 px -> hero 216x303 mm min_px (2552, 3579) 305.7 DPI pass
amenity_clubhouse.jpg 1000x682 px -> amenity_img_b 88x60 mm min_px (1040, 709) 288.6 DPI warn
```

The hero slot is a full page (210 x 297 mm) bleeding on all four edges, so it is measured as 216 x 303 mm. The
clubhouse image has fewer pixels than the 1040 x 709 the slot needs, so it lands in the warn band.

### Print geometry

The page boxes and crop marks of every PDF page. The slug and crop mark numbers are **provisional until the printer
confirms its spec**. All the numbers live in `src/brochure/print_config.py`; `src/brochure/render/geometry.py` computes
the boxes and mark segments from them (pure code, in mm and in points, 1 mm = 72 / 25.4 pt) and refuses a config whose
marks would touch the bleed or leave the MediaBox. Coordinates have their origin at the trim's lower-left corner, as
WeasyPrint writes them, so the BleedBox and MediaBox start at negative values.

| Box | Rule | Size (mm) | PDF box (pt) |
|---|---|---|---|
| TrimBox | A4 portrait | 210 x 297 | [0, 0, 595.276, 841.890] |
| BleedBox | trim + 3 mm (`bleed_mm`) on every edge | 216 x 303 | [-8.504, -8.504, 603.780, 850.394] |
| MediaBox | bleed + 10 mm slug (`slug_beyond_bleed_mm`, measured from the bleed edge) on every edge | 236 x 323 | [-36.850, -36.850, 632.126, 878.740] |

Crop marks: two per corner (one horizontal, one vertical) on the extensions of the trim lines, 0.25 pt black lines
(`crop_mark_weight_pt`), 5 mm (14.173 pt) long (`crop_mark_length_mm`). Each starts 5 mm (14.173 pt) from the trim edge
(`crop_mark_offset_mm`) and ends 10 mm (28.346 pt) from it, so it is 2 mm clear of the bleed and ends 3 mm inside the
MediaBox. The page count must be a positive multiple of 4 (`page_count_multiple`), otherwise `ValueError`.

How the PDF gets these boxes (`src/brochure/render/pdf.py`): WeasyPrint's `@page { bleed: B }` makes the MediaBox the
trim grown by B, so B is set to bleed + slug (13 mm). WeasyPrint caps its BleedBox at 10 pt (3.53 mm) outside the
trim, so a `write_pdf` finisher rewrites every page's BleedBox to the 3 mm bleed. WeasyPrint's own `marks: crop` draws
0.75 pt lines from the media edge in to B / 2, which cannot be changed, so it is off and the marks are drawn as vector
lines (SVG) from the geometry.

Make a blank proof to look at (8 pages, light blue over the bleed box, a thin line on the trim, crop marks, the page
number in the middle; git-ignored):

```
~/.venvs/brochure/bin/python tools/make_blank_pdf.py                 # writes sample/blank-8pp.pdf
~/.venvs/brochure/bin/python tools/make_blank_pdf.py --out out/proof.pdf --pages 12
```

The geometry's unit tests run in CI. The PDF is checked by integration tests in WSL (pypdf reads the boxes of every
page; Ghostscript renders page 1 at 100 DPI and Pillow checks the fill at the bleed edge, the white gap and slug, and the
mark pixels):

```
~/.venvs/brochure/bin/python -m pytest tests/integration/test_blank_pdf.py -rs
```

The proof's page number uses a system sans-serif font (the proof is about geometry). The proof is RGB; CMYK
conversion is not built yet.

## 8. Templates and slots

A template lives in `templates/<template_id>/`: `slots.json` (the shared contract), `layout_rules.json` (section 3),
`positions.json`, `brochure.html.j2` and `brochure.css` (below, "Template and renderer").
Each slot has `id`, `type` (`image`, `text` or `qr`), `page`, `width_mm`, `height_mm`, `bleed_edges` (any of `top`,
`right`, `bottom`, `left`; empty when the slot is inside the trim), `char_budget` (text slots only) and an optional
`comment`. Sizes are the trim-side size; the loader adds the bleed from the config.

```json
{
  "id": "hero",
  "type": "image",
  "page": 1,
  "width_mm": 210,
  "height_mm": 297,
  "bleed_edges": ["top", "right", "bottom", "left"],
  "comment": "Full-page cover image, bleeds off all four edges."
}
```

`min_px` is never stored in the file. `load_slots` in `src/brochure/slots.py` computes it for image slots; a file that
contains `min_px` is rejected.

`classic-8pp` has 33 slots (14 image, 18 text, 1 QR):

| Page | Content | Slots |
|---|---|---|
| 1 | Cover | `hero` (full bleed), `cover_logo`, `cover_title`, `cover_tagline`, `cover_rera_line` |
| 2 | Overview | `overview_img` (bleeds top, left, right), `overview_headline`, `overview_intro`, `overview_highlights` |
| 3 | Location | `location_map`, `location_img`, `location_address`, `location_landmarks` |
| 4 | Amenities | `amenity_img_a`, `amenity_img_b`, `amenity_img_c`, `amenities_list`, `amenities_blurb` |
| 5 | Configurations and floor plans | `plan_img_a`, `plan_img_b`, `config_table`, `plan_note` |
| 6 | Specifications | `spec_banner` (bleeds top, left, right), `spec_img`, `specs_list` |
| 7 | About the developer | `about_img`, `about_headline`, `about_text` |
| 8 | Back cover | `back_logo`, `rera_number`, `rera_qr`, `contact_block`, `disclaimer` |

The QR slot `rera_qr` is 25 x 25 mm. That size is provisional: compliance has not given a minimum QR size for RERA,
and the slot's comment says so.

### Template and renderer

`render_brochure(spec, brand_kit, image_tags, image_dir, out_dir)` in `src/brochure/render/pdf.py` returns
`(pdf_path, page_image_paths)`. It writes `out_dir/brochure.pdf` with WeasyPrint (imported inside the function, so the
unit tests run without Pango), with the page rule, crop marks and BleedBox finisher of the blank proof (section 7), and
`out_dir/page-<n>.png`, one per page in page order, rendered by Ghostscript (found as `brochure doctor` finds it) at
100 DPI and cropped to the TrimBox (`-dUseTrimBox`): the page as it is after cutting, 827 x 1169 px, with no bleed,
slug or crop marks. `render_with_issues(...)` takes the same arguments and also returns the render's issues. Images are read from `image_dir` + each image's path; a missing
file stops the render before WeasyPrint runs. Nothing is written to the image files: cropping is CSS only.

**Positions** (`templates/classic-8pp/positions.json`, owned by the template, not a shared contract). For every slot:
`x_mm`, `y_mm` of the top-left corner of its trim-side box (its `slots.json` size), from the trim's top-left corner,
y downwards; and for text slots a `role` (`title`, `heading`, `subheading`, `body`, `list`, `small-print`). Width and
height always come from `slots.json`. `overlays` lists the slots drawn on top of another by design. An image slot may
name its `caption` corner (`top-right`, or `bottom-right` by default). `decorations` are the colour bands behind the
slots (the cover band, the thin top band). `static_text` is words that belong to the template and are not slots: the
section titles "Location", "Amenities", "Floor plans" and "Specifications" on pages 3 to 6 (heading style with the gold
rule) and "Scan for RERA registration details" under the QR code (small print). `position_problems()`
(`src/brochure/render/positions.py`) checks, in unit tests and every time a brochure is rendered:

- every slot has exactly one position and every position names a slot; text slots have a known role, others none;
- bleed: on each edge in `bleed_edges` the trim-side box lies exactly on the trim edge, so the drawn box (grown by
  `bleed_mm` on that edge only, the size `slots.py` measures) ends exactly 3 mm past the trim; on every other edge it
  lies strictly inside the trim, never touching it. A slot with no `bleed_edges` therefore lies inside the trim;
- text and QR slots lie inside the safe area: the trim inset by `safe_margin_mm` (10 mm, provisional, in
  `print_config.py`);
- no two slots on a page overlap (touching is allowed) except the pairs in `overlays`, and only a text, QR or logo
  slot may be listed on a non-logo image slot. A listed pair must overlap. In `classic-8pp` the four cover slots
  (`cover_logo`, `cover_title`, `cover_tagline`, `cover_rera_line`) lie on the hero. The logo is listed although it is
  an image slot: it sits on the photo by design;
- any non-logo image may turn out to be a render, so each has a caption box (`caption_rect()`, 27 x 4.5 mm, in the corner
  its position names). The box lies inside the image and outside every slot listed over it and every decoration on the
  page. The hero's caption is therefore top-right, above the cover band;
- static text has a known role, lies inside the safe area and overlaps no slot and no other static text.

A separate design rule, `gap_problems()`, is checked in tests on the box positions and, on the rendered sample, on the
measured text: the white space between consecutive blocks on a page stays within `max_block_gap_mm` (15 mm, in
`print_config.py`), except above a block named in `free_gap_above` (the disclaimer, which sits at the foot of page 8).

**Design** (`brochure.html.j2` + `brochure.css`; option "clean and plain"). Each slot is an absolutely positioned box
in mm. Headings are Inter SemiBold (title Inter Bold, 30 pt), body Open Sans 10 pt with 1.5 line spacing, small print
7.5 pt. The brand kit's `primary` colour (navy `#1F3A5F` in the sample) is used for the cover band behind the title,
a thin band bleeding off the top of pages 3, 4, 5, 7 and 8, headings and list labels; the
`accent` colour (gold `#C8A24A`) for the line on top of the cover band, the cover tagline, the short rule under each
heading, the list markers and the rule above the disclaimer. If a kit has no colours named `primary` and `accent`, the
first and second colours are used. Brand colours and font families reach the CSS as variables.

- Fonts: `@font-face` rules point at the files in `assets/fonts` only. A brand font that is not bundled is refused
  (`ValueError`); there is no fallback to a system or web font.
- Images fill their slot (`object-fit: cover`). `object-position` is computed from the tag's `focal_point` so the
  crop is centred on it, as far as the image's edges allow (a plain `x% y%` would not centre it).
- Renders (`kind` `render`): an "Artist's impression" caption at the box the positions rule checks, 6.5 pt body font on
  a light background. On an edge that bleeds, the caption sits 13 mm in from the drawn edge (bleed + safe margin).
- An image slot the layout left unfilled: a light neutral frame with "Image needed".
- Text: newlines become line breaks; `list` slots become one list item per line (two columns for
  `overview_highlights` and `amenities_list`; in `specs_list` the text before ": " is set as a label). `rera_number`
  is printed after "RERA No.". Text boxes never clip.
- Logos: the brand kit's `logo_path` (SVG or PNG, relative to `brand_dir`, the `sample/` folder in the pipeline) when
  the file exists, otherwise the company name in the heading font. Text inside an SVG logo must name a bundled family,
  or WeasyPrint embeds a system font; the sample logo's text is set in Inter.
- QR: the `qrcode` package, vector SVG (one path, no raster), error correction M, quiet zone of 4 modules, at the
  slot's 25 mm.

**Text overflow.** WeasyPrint's public `Page.anchors` gives the position of every element with an `id`. Each text slot
holds an empty start mark and end mark; the distance between them is the height of its text. Text taller than the slot
(by more than `text_overflow_tolerance_mm`, 0.5 mm) becomes a `render.text_overflow` warning routed to `copywriter`,
with its page. The warnings are written to `out_dir/render_issues.json` (an empty list when there are none), logged,
and returned in `RenderResult.issues`. The graph's renderer node puts them in `qa_issues` (nothing reads that field
between the renderer and QA, and the QA step replaces it), so the QA step sees them; `ScriptedQA` returns the
`render.*` issues it finds there together with its scripted ones. A `render.text_overflow` therefore sends the run back
to the copywriter like any QA issue, within the 3-round limit, and one still there after the 3rd round ends up in
`spec.qa_warnings`. No contract changed: `PipelineState` has no new field. The real QA critic must do the same as the
stub.

**In the pipeline.** `real_agents()` uses `RealRenderer`, which writes into `out/<thread id>/` (git-ignored; outside a
graph run, `out/run-<time>-<id>/`). `real_agents(out_root=...)` changes the folder. `stub_agents()` keeps the stub,
because CI has no Pango; graph tests of `real_agents()` pass the stub renderer.

Render the sample (WSL; generates `sample/images/` if any image is missing):

```
~/.venvs/brochure/bin/python tools/render_sample.py                 # writes out/sample/brochure.pdf and page-1..8.png
~/.venvs/brochure/bin/python tools/render_sample.py --out /tmp/x    # writes /tmp/x/sample/...
```

It runs the graph with the stub brief, vision and copy (no LLM), the real layout and the real renderer, stops at human
review, and prints the PDF path, the PNG paths and every warning (the layout's, then any text overflow). A copy of the
8 PNGs (100 DPI, trim size, 0.33 MB in all) is committed in `sample/pages/` for QA critic work. The integration tests render the
sample and check the page count, every page's boxes, that only Inter and Open Sans are embedded, the extracted text
(RERA number on pages 1 and 8, project name on page 1, disclaimer on page 8, "Artist's impression" on exactly the
pages with a render, the section titles, the QR label), the 8 PNGs (trim size within 1 px, no crop-mark black in the
corners), that the hero reaches the bleed edge on page 1 (on a MediaBox rendering of page 1 that the test makes itself),
that the cover caption shows, that no text slot of the sample is under 60% full, and the measured gaps:

```
~/.venvs/brochure/bin/python -m pytest tests/integration/test_render_brochure.py -rs
```

### Fonts

`assets/fonts/Inter/` (Inter 18pt Regular, SemiBold, Bold) and `assets/fonts/OpenSans/` (Regular, Italic, SemiBold,
Bold): static TTFs from the Google Fonts downloads, each folder with its `OFL.txt` (SIL Open Font License 1.1).
Variable fonts and other weights are not kept. 1.57 MB in all. `src/brochure/fonts.py` lists the faces;
`brochure doctor` checks that each file and licence is there. The sample brand kit uses Inter for headings and Open
Sans for body text.

## 9. LLM interface and testing without a network

`src/brochure/llm/` has:

- `LLMClient`: a protocol with `complete(task, payload, images=None) -> dict`. `task` names the agent step, for
  example `"brief.extract"`.
- `OpenAICompatibleClient`: the real client, on the `openai` SDK pointed at any OpenAI-compatible base URL. The task
  name selects a system prompt and an optional JSON Schema (`brochure.agents.TASKS`). Temperature is 0. On a model that
  supports strict structured outputs it sends `response_format: json_schema` with `strict: true`; on any other model it
  sends JSON-object mode with the schema in the system message. Either way the reply is parsed to a dict and the caller
  validates it. HTTP 429 is retried (3 attempts in all, waiting for `Retry-After`, else 1 s then 2 s, at most 60 s),
  then `LLMRateLimited` is raised. Other HTTP errors, timeouts and connection failures raise `LLMError`; a reply that
  is not a JSON object raises `LLMBadReply` (an `LLMError`). The API key is never put in an error message or a log.
  A task can ask for `reasoning_effort` (`TaskSpec.reasoning_effort`); it is sent only to `openai/gpt-oss-*` models.
  The copy task asks for `low`: at the default, gpt-oss can spend its whole output budget thinking and Groq answers
  HTTP 400 `json_validate_failed`.
  `images=` raises `NotImplementedError` for now.
- `FakeLLM`: returns canned responses keyed by task, records every call (`llm.calls`), and raises
  `MissingCannedResponse` naming the task when it has no answer.
- `Agent[I, O]`: a typing-only protocol. An agent is a function `(inputs, llm) -> schema object`. The stub agents are in
  `src/brochure/pipeline/stubs.py`; the real agents are Brief (`src/brochure/agents/brief.py`) and Copywriter (`src/brochure/agents/copywriter.py`).

Unit tests never touch the network. Anything that would call a model uses `FakeLLM` (or the real client over a fake
HTTP transport). The `llm` pytest marker is for tests that call a real model; CI excludes it.

### Configuring the LLM

The real client is configured by three environment variables. Only the key is required.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_API_KEY` | none | The provider's API key. |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible base URL. |
| `LLM_MODEL` | `openai/gpt-oss-120b` | A model on that provider. Groq documents this one as supporting strict `json_schema`. |

`.env.example` lists the names with no values; copy it to `.env` (git-ignored) and fill it in. The program reads
`os.environ` only, so export the values into your shell first (`set -a; . ./.env; set +a`).

To get a free Groq key, sign in at https://console.groq.com and create a key under API Keys. Rate limits depend on your
plan (see Groq's rate-limits page); the client waits and retries on HTTP 429 and gives up after three attempts.

```python
from brochure.agents import llm_from_env
from brochure.pipeline import build_graph, memory_checkpointer, real_agents

llm = llm_from_env()
graph = build_graph(real_agents(), memory_checkpointer(), llm)  # every real step uses this one llm
```

The supported way to run the code and the tests is the WSL virtualenv from [CONTRIBUTING.md](CONTRIBUTING.md#setup-wsl-ubuntu)
(`~/.venvs/brochure`). Any other environment, such as the Windows `.venv`, needs `pip install -e ".[dev]"` first, or
imports of `brochure.llm` fail on the `openai` dependency.

Run the live test (it calls the real model on `sample/brief_sparse.json`):

```
~/.venvs/brochure/bin/python -m pytest -m llm -rs
```

Without `LLM_API_KEY` it skips with that reason. With a key it passes only if the model was called, the agent did not
fall back to the form, the RERA number, possession date and both configurations the prompt states were filled, the
location (which the prompt never mentions) is still empty, and every filled value is in the prompt. It prints which
fields the model filled and how many calls were made, never the key.

The Copywriter has its own live test, `tests/llm/test_copy_live.py` (the sample project, the real client). It passes only
if every one of the 7 owned slots is filled, every code check passes, no fallback warning was logged and there were
at most four calls. It prints each slot with its length and budget, whether it was trimmed, and the call count, never the key. Groq's free tier
allows 8000 tokens a minute for `openai/gpt-oss-120b`; one copy call is 2500 to 3000, so wait a few seconds between runs.

This example was run from the repo root:

```python
from brochure.contracts.images import ImageTag
from brochure.llm import Agent, FakeLLM, LLMClient, MissingCannedResponse


def tag_image(inputs: dict, llm: LLMClient) -> ImageTag:
    return ImageTag.model_validate(llm.complete("vision.tag", inputs))


llm = FakeLLM({"vision.tag": {
    "path": "pool.jpg", "kind": "render", "subject": "Infinity pool", "width_px": 2200, "height_px": 1150,
    "quality": "good", "features": ["pool"], "focal_point": {"x": 0.5, "y": 0.5},
}})
agent: Agent[dict, ImageTag] = tag_image
tag = agent({"path": "pool.jpg"}, llm)
print(tag.subject, [(c.task, c.payload) for c in llm.calls])

try:
    llm.complete("copy.write", {})
except MissingCannedResponse as error:
    print(error)
```

```
Infinity pool [('vision.tag', {'path': 'pool.jpg'})]
FakeLLM has no canned response for task 'copy.write' (it has: vision.tag)
```

## 10. The sample project

"Aurelia Heights" is a fictional project by a fictional developer, Kestrel Urbanscapes, in Pune. Its RERA number is a
placeholder (`P99999000000 (SAMPLE)`).

| File | What it is |
|---|---|
| `sample/brand_kit.json` | A `BrandKit`. |
| `sample/brief.json` | A `Brief`. The form is complete, so it converts to `ProjectFacts` unchanged. |
| `sample/brief_sparse.json` | The same project with a form that leaves out the RERA number, the configurations, the possession date and the tone, which the prompt states in words, and the location, which the prompt does not mention. For the Brief agent. |
| `sample/images.json` | An `ImageManifest` of 12 images with pixel sizes and the slot each is meant for. |
| `sample/logo.svg` | The logo the brand kit points to. |
| `sample/stub_copy.json` | Text for the eight copy slots that cannot be derived from the facts or the brand kit; used by the stub copywriter. A unit test runs the real Copywriter's checks on it. |
| `sample/image_tags.json` | An `ImageTag` for each of the 12 images, for code that runs before the Vision agent exists. |
| `sample/images/` | Generated by `tools/make_sample_images.py`; not committed. |

For their intended slots, three images fail the DPI rule and one warns:

| Image | Slot | Effective DPI | Result |
|---|---|---|---|
| `amenity_gym.jpg` | `amenity_img_c` | 230.7 | fail |
| `floorplan_3bhk.jpg` | `plan_img_b` | 207.8 | fail |
| `developer_office.jpg` | `about_img` | 95.2 | fail |
| `amenity_clubhouse.jpg` | `amenity_img_b` | 288.6 | warn |

The other eight pass. Having bad images on purpose lets the QA and Layout code be tested against failures without
needing real photos. A test pins exactly which images fail and which warns. The rule-based layout places none of the
three failing images (their slots stay unfilled, each with an error) and places the clubhouse with a warn-band warning.

## 11. How we work

Full rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

- Test-driven: no production code without a failing test first; the red must fail on an assertion; work in red-green-refactor
  cycles, but commit only when the feature is ready (normally one commit per feature, plus a separate commit for fixes after
  review), and never unless the test run you just did is green.
- Code changes go on a `feature/<name>` or `fix/<name>` branch, cut from the latest `master`.
- Docs-only changes (README, CHANGELOG, CONTRIBUTING wording) may go straight to `master` after the tests pass.
- Merge with `git merge --no-ff` after merging `master` into the branch and running the full suite.
- A change to the shared contracts (`src/brochure/contracts/`, `contracts/json/`, `templates/*/slots.json`) needs
  review by the other developer before it merges.
- Each feature branch adds an entry at the top of `docs/CHANGELOG.md`.

## 12. Glossary

| Term | Meaning |
|---|---|
| Trim | The final size of the page after cutting: 210 x 297 mm for A4. |
| Bleed | Extra artwork (3 mm here) printed beyond the trim so no white edge shows after cutting. |
| Full-bleed | An element that runs to the edge of the page, so it extends into the bleed. |
| Crop marks | Small lines outside the page that show the printer where to cut. |
| DPI | Dots (pixels) per inch. How sharp an image is at its printed size. |
| CMYK | The four inks (cyan, magenta, yellow, black) a printer uses. Screens use RGB, so colours are converted for print. |
| RERA | The Real Estate (Regulation and Development) Act. Each project has a registration number that must appear on marketing material. |
| Carpet area | The usable floor area of a flat inside its walls, without the walls themselves. The unit is sq ft. |
| Slot | A fixed box on a template page that holds one image, one piece of text or a QR code. |
| Artist's impression | A rendered picture of the building, not a photograph. Brochures label these as illustrative. |

## 13. Known limitations and follow-ups

- Logo slots (`cover_logo`, `back_logo`) are image slots, so the DPI rule would apply to them. They need an exemption
  for vector (SVG) logos.
- Apart from the full-page hero, the slot sizes are placeholders.
- The 25 mm QR size is provisional.
- `PipelineState` has no field for the text of a chat edit, so `changes_requested` re-runs layout with no instructions.
- The stub pipeline is hard-wired to `classic-8pp` and the sample files.
- The Brief agent was written against Groq's documentation and tested with fakes. The live test has to be run with a key to confirm the provider accepts the schema.
- The image tools are not in the graph.
- The Copywriter's prompt cannot make a model count characters; a long slot is fixed by the retry, and a slot that fails twice shows `[copy needed: ...]`.
- The copy keeps curly quotes and apostrophes and en and em dashes; Inter and Open Sans have those glyphs. A character the bundled fonts lack would fall back to a system font; the integration test only checks the sample. Typographic spaces and hyphens are normalised to plain ones.
- The Copywriter does not see the brief's free-text prompt, so the user's emphasis (for example "the short walk to the station") does not reach the copy.
- The PDF is RGB. CMYK conversion with Ghostscript is not built.
- The text slot heights are sized to the sample's text plus about 20%, and the char budgets were not changed, so text near its budget no longer fits on most text slots: it is reported as `render.text_overflow`. A verbatim slot cannot be fixed by the copywriter, so its overflow ends up in `spec.qa_warnings`.
- Pages 2, 5 and 7 leave white space at the foot: their images are as large as the sample's pixels allow at 300 DPI, or as the design keeps them (`about_img` is 88 mm wide; floor plans stay square).
- WeasyPrint is pinned to `weasyprint==70.0` because the BleedBox finisher edits WeasyPrint's PDF objects (pydyf)
  directly. Check the boxes again (the integration tests) before moving to another version.
