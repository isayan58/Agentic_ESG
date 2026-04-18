const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333" x 7.5"
pres.author = "Sayan Adhikary";
pres.title = "ESG CoPilot — One-Pager";

// ── Palette ────────────────────────────────────────────────────
const C = {
  darkBg:     "0D3B2E",
  forest:     "145C3C",
  emerald:    "1B8A5A",
  mint:       "4EC987",
  lightMint:  "E8F5EE",
  nearWhite:  "F0F7F4",
  white:      "FFFFFF",
  lightBg:    "F4FAF7",
  cardBg:     "FFFFFF",
  textDark:   "0D2A1E",
  textMid:    "1A4A2E",
  textMuted:  "5A8070",
  amber:      "F5A623",
  coral:      "E85D4A",
  blue:       "2D7DD2",
  purple:     "7B5EA7",
  slate:      "4A6580",
};

const makeShadow = () => ({ type: "outer", blur: 8, offset: 2, angle: 135, color: "000000", opacity: 0.08 });

const W = 13.333, H = 7.5;
const s = pres.addSlide();
s.background = { color: C.lightBg };

// ── Helpers ────────────────────────────────────────────────────
function card(x, y, w, h, accent) {
  s.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: C.cardBg }, line: { color: "D5EBE0", width: 0.5 },
    shadow: makeShadow()
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.06, h,
    fill: { color: accent }, line: { color: accent }
  });
}

function sectionTitle(text, x, y, w, color = C.textMid, size = 13) {
  s.addText(text, {
    x, y, w, h: 0.3,
    fontSize: size, bold: true, color,
    fontFace: "Trebuchet MS", margin: 0
  });
}

// ── HEADER BAND ───────────────────────────────────────────────
s.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 0, w: W, h: 0.95,
  fill: { color: C.darkBg }, line: { color: C.darkBg }
});
s.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 0, w: 0.16, h: H,
  fill: { color: C.mint }, line: { color: C.mint }
});
// Decorative overlay circles
s.addShape(pres.shapes.OVAL, {
  x: 11.0, y: -1.4, w: 3.2, h: 3.2,
  fill: { color: C.forest, transparency: 55 }, line: { color: C.forest, transparency: 55 }
});
s.addShape(pres.shapes.OVAL, {
  x: 12.0, y: -0.6, w: 1.8, h: 1.8,
  fill: { color: C.emerald, transparency: 60 }, line: { color: C.emerald, transparency: 60 }
});

s.addText("ESG CoPilot", {
  x: 0.35, y: 0.12, w: 5.5, h: 0.5,
  fontSize: 28, bold: true, color: C.mint,
  fontFace: "Trebuchet MS", margin: 0
});
s.addText("Transforming ESG from Compliance to Strategic Intelligence", {
  x: 0.35, y: 0.58, w: 8, h: 0.35,
  fontSize: 13, color: C.nearWhite, fontFace: "Calibri", italic: true, margin: 0
});
s.addText("9 Agents  ·  4 Frameworks  ·  30 KPIs  ·  Audit-Ready", {
  x: 8.5, y: 0.2, w: 4.65, h: 0.32,
  fontSize: 12, bold: true, color: C.mint, fontFace: "Calibri", align: "right", margin: 0
});
s.addText("Background  ·  Challenges  ·  Approach  ·  Impact", {
  x: 8.5, y: 0.58, w: 4.65, h: 0.3,
  fontSize: 11, color: C.nearWhite, fontFace: "Calibri", italic: true, align: "right", margin: 0
});

// ══════════════════════════════════════════════════════════════
// ROW 1 — BACKGROUND + CHALLENGES (y: 1.1 – 3.1, height ≈ 2.0)
// ══════════════════════════════════════════════════════════════

// BACKGROUND card (left, spans ~4.1" wide)
card(0.3, 1.1, 4.1, 2.0, C.emerald);
sectionTitle("1.  BACKGROUND", 0.45, 1.18, 3.9, C.emerald, 12);
s.addText([
  { text: "ESG CoPilot", options: { bold: true } },
  { text: " is an agentic AI platform that transforms ESG reporting from a periodic manual task into an always-on intelligent workflow.", options: { breakLine: true } },
  { text: "\n", options: { fontSize: 4, breakLine: true } },
  { text: "Targets: ", options: { bold: true } },
  { text: "India-listed (BRSR) and EU-regulated (CSRD) enterprises.", options: { breakLine: true } },
  { text: "\n", options: { fontSize: 4, breakLine: true } },
  { text: "Demo: GreenTech Solutions — IT Services · 5,200 employees · INR 3,850 Cr · ESG rating BBB → A.", options: { italic: true } },
], {
  x: 0.5, y: 1.5, w: 3.85, h: 1.55,
  fontSize: 10.5, color: C.textDark, fontFace: "Calibri", valign: "top", margin: 0
});

// CHALLENGES card (right of Background)
card(4.55, 1.1, 8.48, 2.0, C.coral);
sectionTitle("2.  CHALLENGES — Why ESG Is Broken Today", 4.7, 1.18, 8.3, C.coral, 12);

const challenges = [
  { n: "1", title: "Data Fragmentation",  color: C.coral,  body: "Silos across SAP, Workday, finance, procurement. Manual spreadsheet reconciliation is slow & error-prone." },
  { n: "2", title: "Framework Complexity",color: C.amber,  body: "BRSR + CSRD + GRI + SASB — different metrics, thresholds, cadences." },
  { n: "3", title: "Reporting Latency",   color: C.blue,   body: "Cycles take weeks or months. Backward-looking, not actionable in real time." },
  { n: "4", title: "Greenwashing Risk",   color: C.purple, body: "Self-reported metrics diverge from ops data. 73%+ integrity gap rate." },
  { n: "5", title: "No Quantified ROI",   color: C.emerald,body: "CFOs need hard numbers — cost savings, carbon tax avoided, CoC reduction." },
];

challenges.forEach(({ n, title, color, body }, i) => {
  const cw = 1.66, cx = 4.7 + i * (cw + 0.04), cy = 1.52;
  // mini card
  s.addShape(pres.shapes.RECTANGLE, {
    x: cx, y: cy, w: cw, h: 1.5,
    fill: { color: C.lightBg }, line: { color: "D5EBE0", width: 0.5 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: cx, y: cy, w: cw, h: 0.06,
    fill: { color }, line: { color }
  });
  // Number badge
  s.addShape(pres.shapes.OVAL, {
    x: cx + 0.08, y: cy + 0.12, w: 0.28, h: 0.28,
    fill: { color }, line: { color }
  });
  s.addText(n, {
    x: cx + 0.08, y: cy + 0.12, w: 0.28, h: 0.28,
    fontSize: 11, bold: true, color: C.white,
    fontFace: "Trebuchet MS", align: "center", valign: "middle", margin: 0
  });
  s.addText(title, {
    x: cx + 0.08, y: cy + 0.44, w: cw - 0.15, h: 0.33,
    fontSize: 10.5, bold: true, color, fontFace: "Trebuchet MS", margin: 0
  });
  s.addText(body, {
    x: cx + 0.08, y: cy + 0.78, w: cw - 0.15, h: 0.68,
    fontSize: 9, color: C.textDark, fontFace: "Calibri", valign: "top", margin: 0
  });
});

// ══════════════════════════════════════════════════════════════
// ROW 2 — APPROACH: AGENTS + DATA + FRAMEWORKS (y: 3.25 – 5.55)
// ══════════════════════════════════════════════════════════════

// 3. APPROACH — 9 Agent Pipeline (left)
card(0.3, 3.25, 5.4, 2.35, C.mint);
sectionTitle("3.  APPROACH — 9-Agent Orchestration Pipeline", 0.45, 3.33, 5.2, C.emerald, 12);

const agents = [
  { n: "Data Collector",      note: "9 connectors · auto-schema",          color: C.mint },
  { n: "Regulatory Tracker",  note: "BRSR · CSRD · GRI · SASB",            color: C.emerald },
  { n: "Carbon Accountant",   note: "Scope 1/2/3 · hotspots",              color: C.blue },
  { n: "Risk Predictor",      note: "Rating · regime · CBAM",              color: C.amber },
  { n: "Audit Agent",         note: "Grade · integrity gap",               color: C.coral },
  { n: "ESG ROI Agent",       note: "Dual ROI · J-curve · IQS",            color: C.purple },
  { n: "Report Generator",    note: "5 report types · narratives",         color: C.emerald },
  { n: "Action Agent",        note: "50+ prioritized actions",             color: C.mint },
  { n: "Stakeholder Agent",   note: "Investor · regulator · public",       color: C.slate },
];
agents.forEach(({ n, note, color }, i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const ax = 0.45 + col * 1.73, ay = 3.68 + row * 0.56;
  s.addShape(pres.shapes.RECTANGLE, {
    x: ax, y: ay, w: 1.68, h: 0.5,
    fill: { color: C.lightBg }, line: { color: "D5EBE0", width: 0.5 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: ax, y: ay, w: 0.06, h: 0.5,
    fill: { color }, line: { color }
  });
  s.addText(`${i + 1}. ${n}`, {
    x: ax + 0.12, y: ay + 0.02, w: 1.55, h: 0.24,
    fontSize: 9.5, bold: true, color: C.textMid, fontFace: "Trebuchet MS", margin: 0
  });
  s.addText(note, {
    x: ax + 0.12, y: ay + 0.26, w: 1.55, h: 0.22,
    fontSize: 8, color: C.textMuted, fontFace: "Calibri", italic: true, margin: 0
  });
});

// 4. DATA LAYER (middle)
card(5.85, 3.25, 3.6, 2.35, C.blue);
sectionTitle("4.  DATA LAYER", 6.0, 3.33, 3.4, C.blue, 12);

s.addText("9 Connector Types", {
  x: 6.0, y: 3.65, w: 3.4, h: 0.25,
  fontSize: 10, bold: true, color: C.textMid, fontFace: "Trebuchet MS", margin: 0
});
s.addText("File Upload · Google Sheets · REST API · SQL DB · AWS S3 · BigQuery · GCS · Azure Blob · Delta Lake", {
  x: 6.0, y: 3.9, w: 3.4, h: 0.6,
  fontSize: 9, color: C.textDark, fontFace: "Calibri", valign: "top", margin: 0
});

s.addText("7 Canonical Schemas (auto-detected)", {
  x: 6.0, y: 4.52, w: 3.4, h: 0.25,
  fontSize: 10, bold: true, color: C.textMid, fontFace: "Trebuchet MS", margin: 0
});
const schemas = [
  { t: "Emissions",    c: C.coral },
  { t: "ESG Metrics",  c: C.mint },
  { t: "Supply Chain", c: C.amber },
  { t: "Energy",       c: C.emerald },
  { t: "Waste",        c: C.blue },
  { t: "Diversity",    c: C.purple },
  { t: "Financials",   c: C.slate },
];
schemas.forEach(({ t, c }, i) => {
  const col = i % 4, row = Math.floor(i / 4);
  const sx = 6.0 + col * 0.85, sy = 4.78 + row * 0.36;
  s.addShape(pres.shapes.RECTANGLE, {
    x: sx, y: sy, w: 0.82, h: 0.32,
    fill: { color: c, transparency: 82 }, line: { color: c, width: 0.75 }
  });
  s.addText(t, {
    x: sx, y: sy, w: 0.82, h: 0.32,
    fontSize: 8, color: C.textDark, fontFace: "Calibri",
    align: "center", valign: "middle", margin: 0
  });
});

// 5. FRAMEWORKS (right)
card(9.6, 3.25, 3.43, 2.35, C.amber);
sectionTitle("5.  COMPLIANCE — 4 Frameworks", 9.75, 3.33, 3.25, C.amber, 12);

const frameworks = [
  { name: "BRSR",  sub: "SEBI · India · Mandatory", body: "12 reqs · GHG · Diversity · CSR", color: C.coral },
  { name: "CSRD",  sub: "EU · ESRS · Mandatory",    body: "11 ESRS · Double materiality",   color: C.amber },
  { name: "GRI",   sub: "Global · Voluntary",        body: "11 standards · GRI 302–414",     color: C.mint },
  { name: "SASB",  sub: "Investor-Focused · Global", body: "10 IT-sector standards",         color: C.blue },
];
frameworks.forEach(({ name, sub, body, color }, i) => {
  const fy = 3.65 + i * 0.47;
  s.addShape(pres.shapes.RECTANGLE, {
    x: 9.75, y: fy, w: 3.12, h: 0.42,
    fill: { color: C.lightBg }, line: { color: "D5EBE0", width: 0.5 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 9.75, y: fy, w: 0.06, h: 0.42,
    fill: { color }, line: { color }
  });
  s.addText(name, {
    x: 9.85, y: fy + 0.03, w: 0.7, h: 0.36,
    fontSize: 11, bold: true, color, fontFace: "Trebuchet MS", valign: "middle", margin: 0
  });
  s.addText(sub, {
    x: 10.55, y: fy + 0.02, w: 2.35, h: 0.2,
    fontSize: 8, color: C.textMuted, fontFace: "Calibri", italic: true, margin: 0
  });
  s.addText(body, {
    x: 10.55, y: fy + 0.2, w: 2.35, h: 0.22,
    fontSize: 8.5, color: C.textDark, fontFace: "Calibri", margin: 0
  });
});

// ══════════════════════════════════════════════════════════════
// ROW 3 — ROI + IMPACT + KEY STATS (y: 5.65 – 7.2)
// ══════════════════════════════════════════════════════════════

// 6. DUAL ROI (left)
card(0.3, 5.65, 4.8, 1.55, C.purple);
sectionTitle("6.  DUAL ROI FRAMEWORK", 0.45, 5.72, 4.6, C.purple, 12);

// Financial ROI
s.addShape(pres.shapes.RECTANGLE, {
  x: 0.45, y: 6.02, w: 2.12, h: 1.13,
  fill: { color: C.lightMint }, line: { color: C.emerald, width: 0.75 }
});
s.addText("Financial ROI", {
  x: 0.52, y: 6.05, w: 2.0, h: 0.24,
  fontSize: 10, bold: true, color: C.emerald, fontFace: "Trebuchet MS", margin: 0
});
s.addText([
  { text: "INR 1,500 / tCO2e avoided", options: { bullet: true, breakLine: true } },
  { text: "Carbon tax + CBAM avoidance", options: { bullet: true, breakLine: true } },
  { text: "Energy efficiency savings", options: { bullet: true, breakLine: true } },
  { text: "12–24m J-curve payback", options: { bullet: true } },
], {
  x: 0.55, y: 6.28, w: 1.95, h: 0.85,
  fontSize: 8, color: C.textDark, fontFace: "Calibri", valign: "top", margin: 0,
  paraSpaceAfter: 1
});

// Strategic ROI
s.addShape(pres.shapes.RECTANGLE, {
  x: 2.67, y: 6.02, w: 2.33, h: 1.13,
  fill: { color: "E8F0FA" }, line: { color: C.blue, width: 0.75 }
});
s.addText("Strategic ROI", {
  x: 2.74, y: 6.05, w: 2.2, h: 0.24,
  fontSize: 10, bold: true, color: C.blue, fontFace: "Trebuchet MS", margin: 0
});
s.addText([
  { text: "Cost-of-capital reduction (bps)", options: { bullet: true, breakLine: true } },
  { text: "Rating trajectory BBB → A", options: { bullet: true, breakLine: true } },
  { text: "Talent retention savings", options: { bullet: true, breakLine: true } },
  { text: "IQS (0–100) + brand premium", options: { bullet: true } },
], {
  x: 2.77, y: 6.28, w: 2.2, h: 0.85,
  fontSize: 8, color: C.textDark, fontFace: "Calibri", valign: "top", margin: 0,
  paraSpaceAfter: 1
});

// 7. IMPACT — Before / After table (middle)
card(5.25, 5.65, 4.2, 1.55, C.emerald);
sectionTitle("7.  IMPACT — Before  →  After", 5.4, 5.72, 4.0, C.emerald, 12);

const impactRows = [
  ["Cycle",     "Weeks/months",         "Real-time"],
  ["Coverage",  "Single framework",     "4 frameworks simultaneously"],
  ["Audit",     "High exposure",        "Low · integrity-gap detected"],
  ["ROI",       "Anecdotal",            "Dual ROI · quantified · IQS"],
  ["Risk",      "Reactive",             "Predictive · CBAM · scenarios"],
];
impactRows.forEach((row, i) => {
  const ry = 6.05 + i * 0.22;
  const bg = i % 2 === 0 ? C.lightMint : C.cardBg;
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.4, y: ry, w: 3.95, h: 0.21,
    fill: { color: bg }, line: { color: "D5EBE0", width: 0.3 }
  });
  s.addText(row[0], {
    x: 5.45, y: ry + 0.01, w: 0.75, h: 0.19,
    fontSize: 8.5, bold: true, color: C.textMid, fontFace: "Calibri", margin: 0
  });
  s.addText(row[1], {
    x: 6.22, y: ry + 0.01, w: 1.45, h: 0.19,
    fontSize: 8.5, color: C.coral, fontFace: "Calibri", margin: 0
  });
  s.addText("→", {
    x: 7.67, y: ry + 0.01, w: 0.15, h: 0.19,
    fontSize: 9, bold: true, color: C.textMid, fontFace: "Calibri", align: "center", margin: 0
  });
  s.addText(row[2], {
    x: 7.82, y: ry + 0.01, w: 1.55, h: 0.19,
    fontSize: 8.5, bold: true, color: C.emerald, fontFace: "Calibri", margin: 0
  });
});

// 8. KEY STATS (right)
card(9.6, 5.65, 3.43, 1.55, C.mint);
sectionTitle("8.  BY THE NUMBERS", 9.75, 5.72, 3.25, C.mint, 12);

const stats = [
  { v: "80%",    l: "Faster cycles",  c: C.emerald },
  { v: "9",      l: "AI agents",      c: C.blue },
  { v: "73%+",   l: "Integrity gaps", c: C.coral },
  { v: "30",     l: "ESG KPIs",       c: C.amber },
  { v: "4",      l: "Frameworks",     c: C.purple },
  { v: "50+",    l: "Actions/run",    c: C.slate },
];
stats.forEach(({ v, l, c }, i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const sx = 9.75 + col * 1.05, sy = 6.02 + row * 0.56;
  s.addShape(pres.shapes.RECTANGLE, {
    x: sx, y: sy, w: 1.0, h: 0.54,
    fill: { color: c, transparency: 85 }, line: { color: c, width: 0.75 }
  });
  s.addText(v, {
    x: sx, y: sy + 0.01, w: 1.0, h: 0.3,
    fontSize: 15, bold: true, color: c, fontFace: "Trebuchet MS",
    align: "center", margin: 0
  });
  s.addText(l, {
    x: sx, y: sy + 0.31, w: 1.0, h: 0.22,
    fontSize: 7.5, color: C.textDark, fontFace: "Calibri",
    align: "center", margin: 0
  });
});

// ── FOOTER ────────────────────────────────────────────────────
s.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 7.25, w: W, h: 0.25,
  fill: { color: C.darkBg }, line: { color: C.darkBg }
});
s.addText("From compliance checkbox to strategic intelligence  ·  Predictive insights  ·  Quantified ROI  ·  Executable recommendations", {
  x: 0.2, y: 7.27, w: W - 0.4, h: 0.21,
  fontSize: 9, color: C.mint, fontFace: "Calibri", italic: true, align: "center", margin: 0
});

// ── Write file ─────────────────────────────────────────────────
pres.writeFile({ fileName: "ESG_CoPilot_OnePager.pptx" })
  .then(() => console.log("✅  ESG_CoPilot_OnePager.pptx created"))
  .catch(e => { console.error("❌  Error:", e); process.exit(1); });
