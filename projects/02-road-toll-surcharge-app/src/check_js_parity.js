// Extracts the calculation block (between CALC-START and CALC-END) from the demo page,
// runs it on the same synthetic data under Node, and prints totals as JSON.
// Usage: node src/check_js_parity.js
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const site = path.resolve(__dirname, "..", "..", "..", "site", "demos");
const html = fs.readFileSync(path.join(site, "02-road-toll-surcharge-app.html"), "utf8");
const m = html.match(/\/\/ CALC-START([\s\S]*?)\/\/ CALC-END/);
if (!m) throw new Error("CALC block not found in demo page");

const ctx = { window: {} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(site, "data", "02-road-toll.js"), "utf8"), ctx);
vm.runInContext(m[1] + "\nthis.Calc = Calc;", ctx);

const { Calc } = ctx;
const D = ctx.window.TOLL_DATA;
const impact = Calc.customerImpact(D);
const r2 = (x) => Math.round(x * 100) / 100;
const tiers = {};
let toll = 0, rev = 0, sur = 0;
const byCust = {};
for (const c of impact) {
  toll += c.toll; rev += c.revenue;
  byCust[c.id] = r2(c.toll);
  const p = Calc.propose(c, "pct", 100);
  sur += r2(p.surcharge);
  tiers[p.tier] = (tiers[p.tier] || 0) + 1;
}
process.stdout.write(JSON.stringify({
  total_toll_eur: r2(toll), total_revenue_eur: r2(rev), default_surcharge_eur: r2(sur),
  tiers_default_proposal: tiers, toll_by_customer: byCust,
}));
