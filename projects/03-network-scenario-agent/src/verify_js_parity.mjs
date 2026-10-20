// Checks the JavaScript engine in the demo page against the Python baseline.
// Usage (from this folder): node verify_js_parity.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const site = resolve(here, "../../../site/demos");
const html = readFileSync(resolve(site, "03-network-scenario-agent.html"), "utf8");
const code = html.split("// ENGINE START")[1].split("// ENGINE END")[0];
const NetEngine = new Function(code + "; return NetEngine;")();
const base = JSON.parse(readFileSync(resolve(site, "data/03-baseline.json"), "utf8"));

let worst = 0, n = 0, assignDiff = 0;
for (const sc of base.scenarios) {
  const res = NetEngine.runScenario(base.network, sc.overrides);
  const js = NetEngine.summary(res);
  for (const d of ["direct", "milkrun", "crossdock", "bestmix"]) {
    for (const k of ["cost_week", "co2_t_week", "trucks_week", "plant_arrivals_week"]) {
      const py = sc.results[d][k];
      const dev = py ? Math.abs(js[d][k] - py) / Math.abs(py) : 0;
      worst = Math.max(worst, dev); n++;
    }
  }
  for (const [sid, m] of Object.entries(sc.bestmix_assign)) if (res.designs.bestmix.assign[sid] !== m) assignDiff++;
  console.log(`${sc.name}: bestmix JS ${js.bestmix.cost_week.toFixed(2)} vs Python ${sc.results.bestmix.cost_week.toFixed(2)}`);
}
console.log(`values compared: ${n}, max relative deviation: ${(100 * worst).toFixed(5)}%, best-mix supplier mode differences: ${assignDiff}`);
console.log(worst <= 0.005 ? "PASS (within 0.5%)" : "FAIL");
process.exit(worst <= 0.005 ? 0 : 1);
