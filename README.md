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
- Slots format, loader and the `classic-8pp` template (section 8).
- LLM interface with a `FakeLLM` for tests, and a real client for any OpenAI-compatible endpoint (Groq by default) (section 9).
- The Brief and Copywriter agents are real, using the LLM (section 3): Brief fills empty form fields with facts the prompt states; Copywriter writes the free-text slots, checked in code. The other agents are still stubs.
- The pipeline graph (LangGraph), with pause and resume for missing fields and for human review (section 3). `stub_agents()` runs it with no LLM; `real_agents()` swaps in the real Brief and Copywriter agents, which use the client that `build_graph` is given.
- A fictional sample project, "Aurelia Heights" (section 10).
- `brochure doctor`: checks Python, WeasyPrint, Ghostscript and bundled fonts. It is the only CLI command.
- CI on GitHub Actions: runs the unit tests on pushes to `feature/**` and `fix/**` and on pull requests into `master`.

Not built:

- Real agents other than Brief and Copywriter. Vision, Layout and the QA critic are stubs.
- The image tools. They are not in the graph yet.
- The renderer (HTML to PDF, bleed, crop marks, CMYK). The stub returns fake file paths and creates no files.
- Export. The stub does nothing.
- An API and a frontend.
- Checks of images against the DPI rule inside a pipeline. The maths exists; nothing runs it yet. (Text length is checked, for the slots the Copywriter writes.)

## 3. How it will work

This is the design the contracts were written for. The graph that connects the steps is built and runs on stub agents (see "The graph on stub agents" below). The real agents, the image tools and the renderer are not built, and step 3 is not in the graph yet.

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
| 4. Copywriter | Writes the text for each text slot, within its `char_budget`. | Real. `real_agents()` runs the Copywriter agent (one LLM call, a second only for slots that fail a check) for the 8 free-text slots; code fills the other 10 text slots word for word. `stub_agents()` uses sample text. |
| 5. Layout agent | Chooses which image and text goes in which slot and produces the `BrochureSpec`. Also applies the human's chat edits. | Stub: places the sample images and text in every slot. |
| 6. Renderer | Fills the HTML/CSS template from the spec and produces the PDF and one PNG per page. | Stub: fake paths, no files. |
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
- After the renderer, the QA step runs. An issue routed to `copywriter` sends the run back to the copywriter (then
  layout, render, QA); one routed to `layout` goes back to layout; one routed to `none` does not loop. After 3 QA
  passes the run moves on whatever the issues say. Issues that do not loop, and any left after the 3rd pass, are
  written to `spec.qa_warnings`.
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
`ProjectFacts` (without the tone), the company name, each image's `subject` and `features` (no paths), the tone notes,
the owned slots (`id`, `page`, `char_budget`, `comment`) and, when the QA loop sent the run back, the QA issues routed to
the copywriter. Facts are strict, wording is free.

**Which slots it writes.** Text slots of `classic-8pp` are split in two. Code fills the verbatim slots word for word
(`src/brochure/verbatim.py`); the Copywriter never sees or rewrites them, so legal and contact text is never reworded.

| Written by the Copywriter (char budget) | Filled by code from the facts and the brand kit (char budget) |
|---|---|
| `cover_title` (40), `cover_tagline` (90), `overview_headline` (60), `overview_intro` (600), `overview_highlights` (240), `amenities_blurb` (250), `plan_note` (160), `about_headline` (60) | `cover_rera_line` (60), `rera_number` (60), `location_address` (120), `location_landmarks` (400), `amenities_list` (300), `config_table` (400), `specs_list` (700), `about_text` (450), `contact_block` (200), `disclaimer` (500) |

The pipeline step (`pipeline/real.py`) returns the verbatim slots plus whatever the Copywriter wrote as `slot_copy`.

**Checks, per slot, in code** (`src/brochure/agents/copy_checks.py`). Each failure gives a short reason:

- Budget: not empty, and `len(text) <= char_budget`. The reason for a long text names a length to aim for (85% of the
  budget), because a model cannot count characters.
- Numbers: every number (digits, `1,090`, decimals, and number words from one to twenty) must equal a number found
  anywhere in the `ProjectFacts`, including inside strings such as "2 BHK" or "Dec 2028". A thousands group split by a
  non-breaking space counts as one number.
- Names: every capitalised word that does not start a sentence or a line must appear (any case) in the facts, in the
  brand kit's `company_name`, or in the allow-list. This also rejects headlines in Title Case.
- Money: currency symbols and words (`copy_money_words.txt`), as whole words.
- Superlatives and promises: `copy_banned_phrases.txt`, as whole words or phrases ("bestow" is fine).

The three lists are data files in `src/brochure/agents/data/` (`copy_name_allowlist.txt`, `copy_money_words.txt`,
`copy_banned_phrases.txt`): one entry per line, `#` comments, shipped with the package.

**Retry and fallback.** If any slot fails, the model is asked once more with only the failing slots and the reason for
each; slots that passed keep their first text whatever the second reply says. A slot that still fails is left out of
the result and one warning lists it with its reasons. A client error (`LLMRateLimited`, `LLMBadReply`, `LLMError`)
stops the asking, keeps what already passed and logs one warning with the cause. The run never crashes on the model.

**Missing copy.** The layout stub puts the visible text `[copy needed: <slot_id>]` in any text slot with no copy, so the
reviewer sees the gap (the QA critic will later flag these placeholders).

**What the checks cannot see.** Numbers, names, money and superlatives are checked in code. A made-up description with
none of those ("a gym with floor-to-ceiling windows") passes; the prompt forbids it, and only a later reviewer or QA
critic can catch it. The brief's free-text prompt is not sent to the Copywriter.

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
  print_config.py             A4 size, bleed, DPI thresholds
  dpi.py                      min_pixels, effective_dpi, classify_dpi
  slots.py                    load slots.json, compute min_px
  contracts/                  Pydantic models and the schema export
  llm/                        LLMClient, FakeLLM, OpenAICompatibleClient, Agent protocol
  verbatim.py                 the text slots code fills word for word (RERA, contact, lists, about text, disclaimer)
  agents/                     real agents (Brief, Copywriter), their prompt files, the copy checks and their data files
  pipeline/                   LangGraph graph, stub agents, real_agents, checkpointers
templates/classic-8pp/        slots.json for the 8-page template (no HTML/CSS yet)
tests/unit/                   fast tests, no network
tests/integration/            tests that need WeasyPrint or Ghostscript
tests/llm/                    tests that call the real model (marker `llm`, skipped without a key)
tools/                        export_schemas.py, make_sample_images.py
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

The doctor prints one line per check and exits with 1 if any check fails. Python, WeasyPrint and Ghostscript are
checked for real. The bundled-fonts check currently fails because `assets/fonts` is not in the repo yet (see
section 13). Its "git restore" hint does not apply until the fonts are committed.

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

## 8. Templates and slots

A template lives in `templates/<template_id>/`. For now it is only `slots.json`; the HTML and CSS do not exist yet.
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
if every one of the 8 owned slots is filled, every code check passes, no fallback warning was logged and there were
one or two calls. It prints each slot with its length and budget, and the call count, never the key. Groq's free tier
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
| `sample/stub_copy.json` | Text for the eight copy slots that cannot be derived from the facts or the brand kit; used by the stub copywriter. |
| `sample/image_tags.json` | An `ImageTag` for each of the 12 images, for code that runs before the Vision agent exists. |
| `sample/images/` | Generated by `tools/make_sample_images.py`; not committed. |

For their intended slots, three images fail the DPI rule and one warns:

| Image | Slot | Effective DPI | Result |
|---|---|---|---|
| `amenity_gym.jpg` | `amenity_img_c` | 230.7 | fail |
| `floorplan_3bhk.jpg` | `plan_img_b` | 207.8 | fail |
| `developer_office.jpg` | `about_img` | 190.5 | fail |
| `amenity_clubhouse.jpg` | `amenity_img_b` | 288.6 | warn |

The other eight pass. Having bad images on purpose lets the QA and Layout code be tested against failures without
needing real photos. A test pins exactly which images fail and which warns.

## 11. How we work

Full rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

- Test-driven: no production code without a failing test first; the red must fail on an assertion; commit after
  each green cycle.
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
- Models write typographic characters (a narrow no-break space in "780 sq ft", a non-breaking hyphen in "co-working"). Check that the fonts have those glyphs when the renderer exists.
- The Copywriter does not see the brief's free-text prompt, so the user's emphasis (for example "the short walk to the station") does not reach the copy.
- `brochure doctor` fails the fonts check because `assets/fonts` (Playfair Display, Inter) is not in the repo.
- `jinja2`, `qrcode` and `pypdf` are declared in `pyproject.toml` but nothing in the code uses them yet. WeasyPrint
  is only used by the doctor.
- Integration tests only check that WeasyPrint imports and that Ghostscript runs.
