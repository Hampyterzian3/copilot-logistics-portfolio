"""Export the sample RFQ packs for the demo page.

Writes site/demos/data/01-<pack-id>.json (inputs plus the Python checker result, the
reference for the parity check) and refreshes the inline input block in
site/demos/01-tender-desk-copilot.html between DATA-START and DATA-END, so the page works
from file:// without fetch.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import rfq_checker as rc

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parents[1] / "site"
PAGE = SITE / "demos" / "01-tender-desk-copilot.html"
PACKS = ["northwind-europe-2027", "northwind-spares-2027"]


def main() -> None:
    inline = []
    for name in PACKS:
        rows, req, meta = rc.load_pack(ROOT / "data" / name)
        pack = {"meta": meta, "rows": rows, "requirements": req}
        out = dict(pack, result=rc.check(rows, req))
        (SITE / "demos" / "data" / f"01-{name}.json").write_text(
            json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        inline.append(pack)
    payload = json.dumps(inline, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    html = PAGE.read_text(encoding="utf-8")
    block = f'<!--DATA-START--><script type="application/json" id="rfq-packs">{payload}</script><!--DATA-END-->'
    html, n = re.subn(r"<!--DATA-START-->.*?<!--DATA-END-->", lambda _: block, html, flags=re.S)
    if n != 1:
        raise SystemExit("DATA markers not found in demo page")
    PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(f"Exported {len(PACKS)} packs; inline block refreshed in {PAGE.name}")


if __name__ == "__main__":
    main()
