// Builds site/index.html from tools/page.template.html and site/data/projects/*.json.
// No dependencies. Usage: node tools/build-site.mjs [--check]
//   --check  compare with the current site/index.html instead of writing it (exit 1 on a difference)
//
// The template holds everything that is not a project (head, top bar, intro, method,
// contact, scripts). Bump the ?v= cache versions in the template when CSS or JS changes.
// Markers: <!--@RAIL--> section rail links, <!--@TILES--> intro project tiles,
// <!--@PROJECTS--> project panels, {{COUNT_WORD}} number of projects as a word.
//
// One JSON per project, named after its media folder (site/media/NN/). "order" sets the
// position on the page; sections are numbered p01, p02, ... in that order.
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SITE = join(ROOT, "site");
const CHECK = process.argv.includes("--check");
const WORDS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"];

const esc = (s = "") => String(s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
// Element text where quotes stay literal (video descriptions)
const escText = (s = "") => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const pad = n => String(n).padStart(2, "0");
const IMPACT = { acc: "Accuracy", time: "Time", cost: "Cost" };

const dataDir = join(SITE, "data", "projects");
const projects = readdirSync(dataDir)
  .filter(f => /^\d\d\.json$/.test(f))
  .map(f => JSON.parse(readFileSync(join(dataDir, f), "utf8")))
  .sort((a, b) => a.order - b.order);
projects.forEach((p, i) => { p.anchor = pad(i + 1); });

const missing = [];
const checkSrc = (p, src) => { if (src && !/^https?:/.test(src) && !existsSync(join(SITE, src))) missing.push(`${p.id}: ${src}`); };
const ext = href => /^https?:/.test(href || "");

function media(c, p) {
  const t = c.type;
  if (t === "image" || t === "diagram") {
    checkSrc(p, c.src);
    const diagram = c.diagramClass ?? t === "diagram";
    return `<a class="m m-img${diagram ? " m-diagram" : ""}" href="${esc(c.src)}" target="_blank" rel="noopener">
      <img src="${esc(c.src)}" alt="${esc(c.alt || c.title)}" loading="lazy" decoding="async"></a>`;
  }
  if (t === "video") {
    checkSrc(p, c.src); checkSrc(p, c.poster);
    const desc = c.description ? ` aria-describedby="${esc(c.description.id)}"` : "";
    return `<div class="m m-video"><video src="${esc(c.src)}"${c.poster ? ` poster="${esc(c.poster)}"` : ""} muted playsinline loop controls preload="none" aria-label="${esc(c.alt || c.title)}"${desc}></video></div>`;
  }
  if (t === "code") {
    return `<div class="m m-code"><div class="code-bar"><span></span><span></span><span></span><em>${esc(c.lang || "")}</em></div><pre tabindex="0"><code>${esc(c.code)}</code></pre></div>`;
  }
  if (t === "metric") {
    const ms = (c.metrics || []).map(m => `<div class="metric"><span class="mv">${esc(m.value)}</span><span class="ml">${esc(m.label)}</span></div>`).join("");
    return `<div class="m m-metric">${ms}</div>`;
  }
  if (t === "demo") {
    if (!ext(c.href)) checkSrc(p, c.href);
    return `<div class="m m-demo"><img src="assets/brand/hampy-agent-icon.png" alt="" width="72" height="72">
      <a class="btn" href="${esc(c.href)}"${ext(c.href) ? ' target="_blank" rel="noopener"' : ""}>${esc(c.cta || "Open the demo")} <span aria-hidden="true">&rarr;</span></a></div>`;
  }
  if (t === "text") return `<div class="m m-text"><span class="q" aria-hidden="true">&gt;_</span><p>${esc(c.body)}</p></div>`;
  throw new Error(`${p.id}: unknown card type ${t}`);
}

function card(c, i, n, p) {
  const cap = c.caption != null ? `<p class="cap">${esc(c.caption)}</p>` : "";
  const d = c.description;
  const vdesc = d ? `<details class="vdesc"><summary>${esc(d.summary || "Text description of the video")}</summary><p id="${esc(d.id)}">${escText(d.text)}</p></details>` : "";
  return `<li class="shot shot-${esc(c.type)}" aria-roledescription="slide" aria-label="${i + 1} of ${n}: ${esc(c.title)}">
    ${media(c, p)}
    <div class="shot-txt"><h3 class="shot-h"><span class="n">${pad(i + 1)}</span>${esc(c.heading ?? c.title)}</h3>${cap}${vdesc}</div>
  </li>`;
}

function section(p, idx) {
  const n = p.cards.length;
  const stack = p.stack.map(s => typeof s === "string" ? `<li class="chip">${esc(s)}</li>` : `<li class="chip${s.ghost ? " ghost" : ""}">${esc(s.label)}</li>`).join("");
  const links = (p.links || []).map(l => {
    if (!ext(l.href)) checkSrc(p, l.href);
    return `<a class="btn${l.secondary ? " secondary" : ""}" href="${esc(l.href)}"${l.external ? ' target="_blank" rel="noopener"' : ""}>${esc(l.label)}</a>`;
  }).join("");
  const kicker = `Project ${idx + 1} of ${projects.length}${p.kickerNote ? ` · ${esc(p.kickerNote)}` : ""}`;
  return `
<section class="panel project" id="p${p.anchor}" data-title="${esc(p.title)}" aria-labelledby="t${p.anchor}">
  <div class="panel-in">
    <header class="ph">
      <div class="ph-num" aria-hidden="true">${p.anchor}</div>
      <div class="ph-main">
        <p class="kicker">${kicker}</p>
        <h2 id="t${p.anchor}">${esc(p.title)}</h2>
${p.impact?.length ? `        <ul class="impact" aria-label="Impact">${p.impact.map(k => `<li class="imp i-${esc(k)}">${IMPACT[k] || esc(k)}</li>`).join("")}</ul>\n` : ""}        <p class="outcome">${esc(p.outcome)}</p>
        <ul class="stack" aria-label="Stack">${stack}</ul>
      </div>
      <div class="ph-side">
        <p class="summary">${esc(p.summary)}</p>
        <p class="cv">${esc(p.cv)}</p>
        <div class="links">${links}</div>
      </div>
    </header>
    <div class="roll" data-roll role="region" aria-roledescription="carousel" aria-label="${esc(p.title)} snippets">
      <ul class="roll-track" tabindex="0" aria-label="${esc(p.title)} snippets, swipe or use arrow keys">${p.cards.map((c, i) => card(c, i, n, p)).join("")}</ul>
      <div class="roll-ctl">
        <button class="rb prev" type="button" aria-label="Previous snippet">&larr;</button>
        <div class="dots" aria-hidden="true">${p.cards.map(() => "<i></i>").join("")}</div>
        <span class="count" aria-live="polite">1 / ${n}</span>
        <button class="rb next" type="button" aria-label="Next snippet">&rarr;</button>
      </div>
    </div>
  </div>
</section>
`;
}

const tpl = readFileSync(join(ROOT, "tools", "page.template.html"), "utf8");
const html = tpl
  .replace("<!--@RAIL-->", projects.map(p => `<li><a href="#p${p.anchor}"><span>${esc(p.title)}</span></a></li>`).join(""))
  .replace("<!--@TILES-->", projects.map(p => `<a class="hero-tile" href="#p${p.anchor}"><span class="ht-n">${p.anchor}</span><span class="ht-t">${esc(p.title)}</span></a>`).join(""))
  .replace("\n<!--@PROJECTS-->\n", projects.map(section).join(""))
  .replaceAll("{{COUNT_WORD}}", WORDS[projects.length] || String(projects.length));

const out = join(SITE, "index.html");
const summary = `index.html: ${projects.length} projects, ${projects.reduce((a, p) => a + p.cards.length, 0)} cards`;
if (CHECK) {
  const same = existsSync(out) && readFileSync(out, "utf8") === html;
  console.log(same ? `${summary}: up to date` : `${summary}: DIFFERS from site/index.html`);
  if (!same) process.exitCode = 1;
} else {
  writeFileSync(out, html);
  console.log(summary);
}
if (missing.length) { console.log("MISSING FILES:\n  " + missing.join("\n  ")); process.exitCode = 1; }
