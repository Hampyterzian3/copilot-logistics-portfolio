// Parity check: runs the JavaScript rules from the demo page on each exported pack and
// asserts the result equals the Python checker output stored in site/demos/data/01-*.json.
// Also asserts the inputs inlined in the page match the exported JSON inputs.
// Usage: node src/check_parity.js   (prints PARITY OK, exit code 1 on any mismatch)
const fs = require("fs");
const path = require("path");

const site = path.resolve(__dirname, "..", "..", "..", "site");
const page = fs.readFileSync(path.join(site, "demos", "01-tender-desk-copilot.html"), "utf8");

const rules = page.split("// RULES-START")[1]?.split("// RULES-END")[0];
if (!rules) { console.error("RULES markers not found"); process.exit(1); }
const { checkRfq } = new Function(rules + "\nreturn { checkRfq };")();

const inlineMatch = page.match(/<script type="application\/json" id="rfq-packs">([\s\S]*?)<\/script>/);
const inline = JSON.parse(inlineMatch[1]);

// Canonical JSON: sorted keys, so key order never causes a false mismatch.
const canon = (v) => Array.isArray(v) ? v.map(canon)
  : v && typeof v === "object" ? Object.keys(v).sort().reduce((o, k) => (o[k] = canon(v[k]), o), {})
  : v;
const same = (a, b) => JSON.stringify(canon(a)) === JSON.stringify(canon(b));

let failures = 0;
const files = fs.readdirSync(path.join(site, "demos", "data")).filter((f) => /^01-.*\.json$/.test(f));
if (!files.length) { console.error("no 01-*.json files"); process.exit(1); }
for (const f of files) {
  const pack = JSON.parse(fs.readFileSync(path.join(site, "demos", "data", f), "utf8"));
  const js = checkRfq(pack.rows, pack.requirements);
  const ok = same(js, pack.result);
  const twin = inline.find((p) => p.meta.id === pack.meta.id);
  const inputsOk = !!twin && same(twin.rows, pack.rows) && twin.requirements === pack.requirements;
  console.log(`${f}: result ${ok ? "match" : "MISMATCH"}, inline inputs ${inputsOk ? "match" : "MISMATCH"}, ` +
    `${pack.result.gaps.length} gaps, ${pack.result.lanes.length} lanes`);
  if (!ok) {
    for (const k of Object.keys(pack.result)) {
      if (!same(js[k], pack.result[k])) console.log(`  differs in: ${k}`);
    }
  }
  if (!ok || !inputsOk) failures++;
}
console.log(failures ? `PARITY FAILED (${failures})` : `PARITY OK (${files.length} packs)`);
process.exit(failures ? 1 : 0);
