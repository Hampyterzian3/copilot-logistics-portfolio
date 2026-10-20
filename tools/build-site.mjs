// Builds site/index.html from site/data/projects/*.json. No dependencies.
// Usage: node tools/build-site.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SITE = join(ROOT, "site");
const REPO_URL = "https://github.com/Hampyterzian3/copilot-logistics-portfolio";
const SITE_URL = "https://hampy-portfolio.netlify.app";
const BUILD = Date.now().toString(36);

const esc = (s = "") => String(s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const dataDir = join(SITE, "data", "projects");
const projects = readdirSync(dataDir)
  .filter(f => /^\d\d\.json$/.test(f)).sort()
  .map(f => JSON.parse(readFileSync(join(dataDir, f), "utf8")));

const missing = [];
const checkSrc = (p, src) => { if (src && !/^https?:/.test(src) && !existsSync(join(SITE, src))) missing.push(`${p.id}: ${src}`); };

function media(card, p) {
  const t = card.type;
  if (t === "image" || t === "diagram") {
    checkSrc(p, card.src);
    return `<a class="m m-img${t === "diagram" ? " m-diagram" : ""}" href="${esc(card.src)}" target="_blank" rel="noopener">
      <img src="${esc(card.src)}" alt="${esc(card.alt || card.title)}" loading="lazy" decoding="async"></a>`;
  }
  if (t === "video") {
    checkSrc(p, card.src); checkSrc(p, card.poster);
    return `<div class="m m-video"><video src="${esc(card.src)}"${card.poster ? ` poster="${esc(card.poster)}"` : ""} muted playsinline loop controls preload="none" aria-label="${esc(card.alt || card.title)}"></video></div>`;
  }
  if (t === "code") {
    return `<div class="m m-code"><div class="code-bar"><span></span><span></span><span></span><em>${esc(card.lang || "")}</em></div><pre tabindex="0"><code>${esc(card.code)}</code></pre></div>`;
  }
  if (t === "metric") {
    const ms = (card.metrics || []).map(m => `<div class="metric"><span class="mv">${esc(m.value)}</span><span class="ml">${esc(m.label)}</span></div>`).join("");
    return `<div class="m m-metric">${ms}</div>`;
  }
  if (t === "demo") {
    if (card.href && !/^https?:/.test(card.href)) checkSrc(p, card.href);
    const ext = /^https?:/.test(card.href || "");
    return `<div class="m m-demo"><img src="assets/brand/hampy-agent-icon.png" alt="" width="72" height="72">
      <a class="btn" href="${esc(card.href)}"${ext ? ' target="_blank" rel="noopener"' : ""}>${esc(card.cta || "Open the demo")} <span aria-hidden="true">&rarr;</span></a></div>`;
  }
  return `<div class="m m-text"><span class="q" aria-hidden="true">&gt;_</span><p>${esc(card.body || card.caption)}</p></div>`;
}

function card(c, i, n, p) {
  const caption = c.type === "text" && !c.body ? "" : `<p class="cap">${esc(c.caption)}</p>`;
  return `<li class="shot shot-${esc(c.type)}" aria-roledescription="slide" aria-label="${i + 1} of ${n}: ${esc(c.title)}">
    ${media(c, p)}
    <div class="shot-txt"><h4><span class="n">${String(i + 1).padStart(2, "0")}</span>${esc(c.title)}</h4>${caption}</div>
  </li>`;
}

function section(p, idx) {
  const n = p.cards.length;
  const stack = p.stack.map(s => `<li class="chip${/GitHub/.test(s) ? " ghost" : ""}">${esc(s)}</li>`).join("");
  const links = [
    p.demo ? `<a class="btn" href="${esc(p.demo)}">Try the demo</a>` : "",
    p.repo ? `<a class="btn secondary" href="${REPO_URL}/tree/main/${esc(p.repo)}" target="_blank" rel="noopener">Source</a>` : "",
    p.external ? `<a class="btn secondary" href="${esc(p.external.href)}" target="_blank" rel="noopener">${esc(p.external.label)}</a>` : ""
  ].join("");
  if (p.demo) checkSrc(p, p.demo);
  return `
<section class="panel project" id="p${esc(p.id)}" data-title="${esc(p.title)}" aria-labelledby="t${esc(p.id)}">
  <div class="panel-in">
    <header class="ph">
      <div class="ph-num" aria-hidden="true">${esc(p.id)}</div>
      <div class="ph-main">
        <p class="kicker">Project ${idx + 1} of ${projects.length}</p>
        <h2 id="t${esc(p.id)}">${esc(p.title)}</h2>
        <p class="outcome">${esc(p.outcome)}</p>
        <ul class="stack" aria-label="Stack">${stack}</ul>
      </div>
      <div class="ph-side">
        <p class="summary">${esc(p.summary)}</p>
        <p class="cv">${esc(p.cv)}</p>
        <div class="links">${links}</div>
      </div>
    </header>
    <div class="roll" data-roll>
      <ul class="roll-track" tabindex="0" aria-label="${esc(p.title)} snippets, swipe or use arrow keys">${p.cards.map((c, i) => card(c, i, n, p)).join("")}</ul>
      <div class="roll-ctl">
        <button class="rb prev" type="button" aria-label="Previous snippet">&larr;</button>
        <div class="dots" aria-hidden="true">${p.cards.map(() => "<i></i>").join("")}</div>
        <span class="count" aria-live="polite">1 / ${n}</span>
        <button class="rb next" type="button" aria-label="Next snippet">&rarr;</button>
      </div>
    </div>
  </div>
</section>`;
}

const nav = projects.map(p => `<li><a href="#p${esc(p.id)}"><span>${esc(p.title)}</span></a></li>`).join("");
const allStack = ["Microsoft 365 Copilot", "Copilot Studio", "Power Apps", "Power Automate", "Dataverse", "Power BI", "AI Builder", "GitHub Copilot"];

const html = `<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hampy Terzian, AI automation</title>
<meta name="description" content="Eight AI automation projects for logistics and operations, built on Microsoft 365 Copilot, Copilot Studio, Power Platform and GitHub Copilot.">
<meta name="theme-color" content="#0c2c23">
<link rel="icon" href="assets/brand/hampy-favicon-64.png">
<meta property="og:type" content="website">
<meta property="og:title" content="Hampy Terzian, AI automation for logistics">
<meta property="og:description" content="Eight projects on the Microsoft AI stack: Copilot Studio agents, Power Platform apps and flows, and tested code in GitHub Copilot-ready repos.">
<meta property="og:image" content="${SITE_URL}/assets/brand/og.png">
<meta property="og:url" content="${SITE_URL}/">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="assets/css/tokens.css?v=${BUILD}">
<link rel="stylesheet" href="assets/css/site.css?v=${BUILD}">
</head>
<body>
<a class="skip" href="#p01">Skip to projects</a>
<header class="topbar">
  <a href="#top" class="brand"><img src="assets/brand/hampy-logo-offwhite.svg" alt="hampy" height="24"></a>
  <span class="where" aria-live="polite"></span>
  <a class="btn small" href="#contact">Work with me</a>
</header>
<nav class="rail" aria-label="Sections"><ol>
  <li><a href="#top"><span>Intro</span></a></li>${nav}
  <li><a href="#contact"><span>Contact</span></a></li>
</ol></nav>
<main class="snap" id="snap">
<section class="panel hero" id="top" data-title="Intro" aria-labelledby="hero-h">
  <div class="panel-in">
    <p class="kicker">Freelance AI automation consultant · Amsterdam</p>
    <h1 id="hero-h">AI that does the <em>logistics</em> paperwork.</h1>
    <p class="lede">Eight projects built on the Microsoft AI stack. Copilot Studio agents, Power Platform apps and flows, and tested code in GitHub Copilot-ready repos, each grounded in a real problem from a decade in freight forwarding and contract logistics.</p>
    <ul class="stack big" aria-label="Microsoft stack">${allStack.map(s => `<li class="chip">${s}</li>`).join("")}</ul>
    <div class="hero-grid">
      ${projects.map(p => `<a class="hero-tile" href="#p${esc(p.id)}"><span class="ht-n">${esc(p.id)}</span><span class="ht-t">${esc(p.title)}</span></a>`).join("")}
    </div>
    <p class="cue" aria-hidden="true">Scroll <span>&darr;</span> one project per screen, swipe each roll <span>&rarr;</span></p>
  </div>
</section>
${projects.map(section).join("\n")}
<section class="panel contact" id="contact" data-title="Contact" aria-labelledby="c-h">
  <div class="panel-in">
    <img class="mark" src="assets/brand/hampy-agent-icon.png" alt="" width="96" height="96">
    <h2 id="c-h">Have a process that eats your team's week?</h2>
    <p class="lede">I am Hampy Terzian, a solutions design manager in logistics with an industrial engineering background and an MIT MicroMasters in Supply Chain Management. I find the manual work worth automating, build it on the tools you already license, and say plainly when something is not worth automating.</p>
    <div class="links">
      <a class="btn" href="mailto:HampyTerzian3@gmail.com">Email me</a>
      <a class="btn secondary" href="https://www.linkedin.com/in/hampy-terzian-58322ba6" target="_blank" rel="noopener">LinkedIn</a>
      <a class="btn secondary" href="${REPO_URL}" target="_blank" rel="noopener">All source on GitHub</a>
    </div>
    <p class="fine">Bonus: <a href="bonus/process-intake-agent.html">Process Intake Agent</a>, a Copilot Studio agent that interviews a business user about a manual process and recommends the right automation route.</p>
    <p class="fine">Projects 1 to 5 use a fictional company and synthetic data. Demos simulate the agents in the browser; each project folder holds the Copilot Studio, Power Automate and Dataverse artefacts to build them in a tenant.</p>
    <p class="fine">&copy; 2026 Hampy Terzian</p>
  </div>
</section>
</main>
<script src="assets/js/site.js?v=${BUILD}" defer></script>
</body>
</html>
`;

writeFileSync(join(SITE, "index.html"), html);
console.log(`index.html: ${projects.length} projects, ${projects.reduce((a, p) => a + p.cards.length, 0)} cards`);
if (missing.length) { console.log("MISSING FILES:\n  " + missing.join("\n  ")); process.exitCode = 1; }
