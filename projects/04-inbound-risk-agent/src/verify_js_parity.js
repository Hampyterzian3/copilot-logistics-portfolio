// Checks that the JS port (site/demos/js/04-risk-model.js) reproduces the Python export exactly.
// Usage: node src/verify_js_parity.js   (exit code 1 on any mismatch)
"use strict";
const fs = require("fs");
const path = require("path");
const repo = path.resolve(__dirname, "..", "..", "..");
const model = require(path.join(repo, "site", "demos", "js", "04-risk-model.js"));
const data = JSON.parse(fs.readFileSync(path.join(repo, "site", "demos", "data", "04-inbound-risk.json"), "utf8"));
const card = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "teams", "alert-card.json"), "utf8"));

let mismatches = 0;
for (const rec of data.shipments) {
  const js = model.scoreShipment(rec);
  const a = JSON.stringify([js.score, js.band, js.points, js.reasons]);
  const b = JSON.stringify([rec.py.score, rec.py.band, rec.py.points, rec.py.reasons]);
  if (a !== b) {
    mismatches++;
    if (mismatches <= 5) console.log("MISMATCH", rec.shipment_id, "\n js:", a, "\n py:", b);
  }
}
const top = data.shipments.find(r => r.shipment_id === data.card_example_id);
const cardMatch = JSON.stringify(model.buildAlertCard(top, model.scoreShipment(top))) === JSON.stringify(card);
console.log(`shipments checked: ${data.shipments.length}, score/band/reason mismatches: ${mismatches}, alert card identical: ${cardMatch}`);
process.exit(mismatches === 0 && cardMatch ? 0 : 1);
