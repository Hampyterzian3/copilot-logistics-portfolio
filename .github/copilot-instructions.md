# GitHub Copilot instructions

Portfolio of AI automation projects for logistics on the Microsoft stack. Apply these rules to every suggestion, chat answer and agent-mode change.

## Content
- British English. No em dashes or en dashes; use commas, colons or full stops.
- Projects 01 to 05 use the fictional company Contoso Logistics and synthetic data only. Never add real company, client or carrier names, and never real shipment data.
- Results shown on the site must be computed by code in the repo. Do not type figures into pages by hand.
- Label simulations as simulations and designs as designs. Do not claim a Power Platform build was deployed unless it was.

## Code
- Python: standard library first, pure functions for calculations, `pytest` tests next to each project (`projects/0N-*/tests`). Run tests per project: `cd projects/0N-* && python -m pytest`.
- Every demo that ports Python logic to JavaScript keeps a parity check; update both sides together and keep the check passing.
- Site: static HTML, CSS and vanilla JS in `site/`, no build step, no external scripts. Regenerate the home page with `node tools/build-site.mjs` after editing `site/data/projects/*.json`.
- Pages must work at 375 px wide with no horizontal page scroll and no console errors.

## Microsoft artefacts
- Copilot Studio topics: YAML in `copilot-studio/topics/`, agent instructions in `copilot-studio/agent-instructions.md`.
- Power Automate: flow specs in `power-automate/*.md`, definition sketches in `*.json`.
- Dataverse: `dataverse/schema.md` is the source of truth for table and column names; keep flows, Power Fx and topics consistent with it.

## Brand (hampy)
- Colours: green `#0c2c23` canvas, offwhite `#fffdf8` text, orange `#ff6b35` single accent, lime `#81cfb3`, blue `#81a3da`, yellow `#e8d67d`, pink `#da81a7`, surface `#244139`.
- Green ink on any bright fill; never offwhite text on lime, blue, yellow, pink or orange.
- Fonts: Space Grotesk headings, Inter body, Pixelify Sans for display text of 48 px and above.
