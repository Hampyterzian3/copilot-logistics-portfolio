// Run: node --test (from the project folder)
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { contrastRatio, relativeLuminance, grade, resolveValue, flatten, brandRamp, buildBrand } from "../src/build_themes.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOKENS = path.resolve(HERE, "..", "src", "tokens");

test("contrast maths matches WCAG reference values", () => {
  assert.equal(relativeLuminance("#000000"), 0);
  assert.equal(relativeLuminance("#ffffff"), 1);
  assert.equal(contrastRatio("#000000", "#ffffff"), 21);
  assert.equal(contrastRatio("#ffffff", "#000000"), 21, "order does not matter");
  assert.equal(contrastRatio("#0c2c23", "#0c2c23"), 1);
  assert.ok(Math.abs(contrastRatio("#767676", "#ffffff") - 4.54) < 0.01, "#767676 on white is the classic 4.54:1");
  assert.ok(Math.abs(contrastRatio("#777777", "#ffffff") - 4.48) < 0.01);
  assert.equal(contrastRatio("#fff", "#000"), 21, "3-digit hex");
});

test("grading thresholds", () => {
  assert.deepEqual(grade(4.5), { pass: true, level: "AA" });
  assert.deepEqual(grade(4.49), { pass: false, level: "AA large only" });
  assert.deepEqual(grade(3, true), { pass: true, level: "AA" });
  assert.deepEqual(grade(7.1), { pass: true, level: "AAA" });
  assert.equal(grade(2.9).pass, false);
});

test("alias resolution and cycle detection", () => {
  const flat = flatten({ color: { $type: "color", a: { $value: "#112233" } }, role: { x: { $value: "{color.a}" }, y: { $value: "{role.x}" } } });
  assert.equal(flat["color.a"].type, "color");
  assert.equal(resolveValue("{role.y}", flat), "#112233");
  const loop = flatten({ a: { $value: "{b}" }, b: { $value: "{a}" } });
  assert.throws(() => resolveValue("{a}", loop), /Circular/);
  assert.throws(() => resolveValue("{nope}", flat), /Unknown/);
});

test("brand ramp has 16 shades with the base at 80", () => {
  const r = brandRamp("#1e1450");
  assert.equal(Object.keys(r).length, 16);
  assert.equal(r["80"], "#1e1450");
  assert.ok(relativeLuminance(r["10"]) < relativeLuminance(r["80"]));
  assert.ok(relativeLuminance(r["160"]) > relativeLuminance(r["80"]));
});

for (const file of ["hampy.tokens.json", "corporate-dpworld.tokens.json"]) {
  test(`output shape: ${file}`, () => {
    const tmp = fs.mkdtempSync(path.join(HERE, ".tmp-"));
    const b = buildBrand(path.join(TOKENS, file), tmp);
    for (const f of ["tokens.css", "tailwind.theme.js", "powerapps-theme.json", "office-theme1.xml", "contrast.md"]) {
      assert.ok(fs.existsSync(path.join(tmp, b.id, f)), `${f} written`);
    }
    assert.match(b.outputs["tokens.css"], /:root \{[\s\S]*--role-accent: var\(--color-[a-z-]+\);/);
    const pa = JSON.parse(b.outputs["powerapps-theme.json"]);
    assert.deepEqual(Object.keys(pa.palette), ["10", "20", "30", "40", "50", "60", "70", "80", "90", "100", "110", "120", "130", "140", "150", "160"]);
    for (const v of Object.values(pa.palette)) assert.match(v, /^#[0-9a-f]{6}$/);
    const xml = b.outputs["office-theme1.xml"];
    for (const slot of ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"]) {
      assert.match(xml, new RegExp(`<a:${slot}><a:srgbClr val="[0-9A-F]{6}"/></a:${slot}>`), slot);
    }
    assert.match(xml, /<a:majorFont><a:latin typeface="[^"]+"\/>/);
    const tw = { exports: {} };
    new Function("module", b.outputs["tailwind.theme.js"])(tw);
    assert.ok(tw.exports.theme.extend.colors.role.accent.startsWith("#"));
    assert.ok(b.contrast.length >= 8);
    for (const p of b.contrast) assert.ok(p.ratio >= 1 && p.ratio <= 21);
    fs.rmSync(tmp, { recursive: true, force: true });
  });
}

test("hampy guide rules hold: no unexpected fails, banned pairs fail", () => {
  const b = buildBrand(path.join(TOKENS, "hampy.tokens.json"), fs.mkdtempSync(path.join(HERE, ".tmp-")));
  assert.equal(b.fails, 0);
  fs.rmSync(path.dirname(b.dir), { recursive: true, force: true });
  for (const p of b.contrast.filter((x) => x.expectFail)) assert.ok(p.status.startsWith("OK"), p.label);
});
