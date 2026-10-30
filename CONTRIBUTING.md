# Contributing

This repo builds print-ready real estate brochures (8 pages, A4 portrait, 3 mm bleed, 300 DPI target). The shared
contracts live in `src/brochure/contracts/`; read them first, they are the interface between everyone's work.

## Setup (WSL, Ubuntu)

WeasyPrint and Ghostscript run in WSL. The Linux virtualenv lives outside the repo.

```
sudo apt install ghostscript libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0   # system libraries
python3.12 -m venv ~/.venvs/brochure
~/.venvs/brochure/bin/python -m pip install -e ".[dev]"
cd "/mnt/<drive>/<path to this repo>"
~/.venvs/brochure/bin/brochure doctor                              # tells you what is still missing, with the fix command
```

Generate the sample images once (they are git-ignored):

```
~/.venvs/brochure/bin/python tools/make_sample_images.py          # writes 12 JPEGs to sample/images/
```

## Running tests

```
~/.venvs/brochure/bin/python -m pytest                       # everything; integration tests skip, with a reason, if a tool is missing
~/.venvs/brochure/bin/python -m pytest -m "not integration"  # fast, pure-logic tests only
~/.venvs/brochure/bin/python -m pytest -m integration        # only tests that need WeasyPrint or Ghostscript
~/.venvs/brochure/bin/python -m pytest -rs                   # also print the reason for every skip
```

CI (`.github/workflows/tests.yml`) runs the unit suite (`python -m pytest -m "not integration"`) on every push to a `feature/**` or `fix/**` branch and on every pull request into `master`. A failing `tests` check blocks a merge.

Markers (registered in `pyproject.toml`; unknown markers are an error):

| Marker | Meaning |
|---|---|
| `integration` | Needs a real external tool (WeasyPrint, Ghostscript). Must skip with a clear reason when the tool is missing; a skip must never look like a pass. |
| `llm` | Calls a real LLM (network, API key). Never in unit tests. Deselect with `-m "not llm"`. |
| `slow` | Takes more than a second or two. |

**Unit tests never touch the network.** Anything that would call a model uses `FakeLLM` (`brochure.llm`), which returns
canned answers keyed by task and records every call.

## Test-driven development

- No production code without a failing test first. Red, green, refactor, one behaviour per cycle.
- The red must fail on an assertion (or an expected exception that is not raised), not on an `ImportError`. Create the empty module or stub first if needed.
- Look at the failing run before you implement, then at the passing run.
- Test behaviour and properties (page count, PDF boxes, extracted text, image placement), not byte-exact PDFs.
- One test per cycle for anything involving DPI, millimetres or pixels. Test the boundaries (for DPI: 300, 299.99, 250, 249.99).
- Pure logic gets fast unit tests with no I/O beyond temp dirs. Tests that need WeasyPrint or Ghostscript go in `tests/integration/` with `@pytest.mark.integration`.
- A bug gets a failing test that reproduces it before the fix.
- Never delete or weaken a test to get green without saying so in the commit message or PR.
- Commit after each green step, with a plain message describing the change.

## Branching and merging

- `master` is always green and is never committed to directly.
- One branch per feature or bug: `feature/<short-name>` or `fix/<short-name>`, cut from the latest `master`.
- Commit after each green TDD cycle, as described above.
- Before merging: merge `master` into your branch, run the full test suite, and make sure it passes.
- Merge into `master` with a merge commit (`git merge --no-ff`), not a squash, so the per-cycle history is kept. Delete the branch after merging.
- A change to the shared contracts needs review by the other developer before it merges. The shared contracts are `src/brochure/contracts/`, `contracts/json/` and `templates/*/slots.json`. If you change a model, regenerate `contracts/json/` with `tools/export_schemas.py` in the same branch.
- Each feature branch adds its own entry at the top of `docs/CHANGELOG.md`.

## Print numbers live in one place

`src/brochure/print_config.py` holds the A4 size, the bleed (3 mm) and the DPI thresholds (pass at 300, warn from 250).
Code and tests read them from there; do not repeat the numbers elsewhere. Pixel maths is in `src/brochure/dpi.py`:

- effective DPI = `min(img_w_px / slot_w_in, img_h_px / slot_h_in)`, where the slot size includes 3 mm for every edge in the slot's `bleed_edges`
- `min_px = ceil(slot size in inches, bleed included, x 300)`
- pass at 300 DPI or more, warn from 250 up to (not including) 300, fail below 250

## Contracts

All contract models inherit `ContractModel` (`extra="forbid"`), so a typo in a JSON file fails loudly. Field names are
plain snake_case and stable: the frontend generates its types from the JSON Schemas.

After changing a model, regenerate the committed schemas and commit them with the change:

```
~/.venvs/brochure/bin/python tools/export_schemas.py        # writes contracts/json/*.json
```

A test fails, and says this command, if `contracts/json/` is out of date.

## Templates and slots

`templates/<template_id>/slots.json` lists every slot: `id`, `type` (`image`, `text`, `qr`), `page`, `width_mm`,
`height_mm`, `bleed_edges` (any of `top`, `right`, `bottom`, `left`; empty for slots inside the trim), `char_budget`
(text slots only) and an optional `comment`. Sizes are the trim-side size; the bleed is added from the config.
`min_px` is never written in the file: `brochure.slots.load_slots` computes it.

## Sample project

`sample/` holds a fictional project ("Aurelia Heights"): `brand_kit.json`, `brief.json`, `images.json` (the image
manifest) and `logo.svg`. `tests/fixtures/image_tags.json` holds the image tags for the 12 images, for code that needs
tags before the vision step exists. The sample deliberately contains three images below 250 DPI and one in the warn
band for their intended slot; a test pins which.
