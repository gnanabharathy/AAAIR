# WP5: Socio-technical assets, ethics and governance

Work Package 5 curates the ethical frameworks, governance instruments, compliance
templates and best-practice guidance that apply to advanced analytics and AI in
Australian health research.

WP5 contains **no software**. Everything in this work package is a document, a
template or a reference framework. Where this README uses the word "tool", it means
a governance or compliance instrument, not a piece of code. If you are looking for
the project's executable prototypes, see [WP6](../WP6).

## Contents

```
WP5/
└── 05 Ethics & Governance (WP 5)/
    ├── WP5 Deliverables/                  7 files, the WP5 outputs
    └── Literature Guides Frameworks/     38 files, the supporting reference library
        ├── Dept of Industry Guide and Template/
        └── National AI Centre Guides/
```

45 files in total.

## Deliverables

| File | What it is |
|------|------------|
| `WP5.2 Ethics and Governance SUBMITTED v1.0.docx` / `.pdf` | The submitted WP5.2 report, *Assessment and Prioritisation of Ethics and Governance Assets*, dated 16 December 2025 |
| `AAAIR Ethics and Governance Matrix with Licensing asof 20260615 v1.1.docx` / `.pdf` | The ranked matrix of Australian governance instruments, version 1.1, position as at 15 June 2026 |
| `Appendix A - Table of AI Guidance v1.0 as of 202604.docx` | Applicable guides and frameworks for data and AI governance in Australia |
| `Appendix B - AU Gov Guidance on AI use as of 20251215.docx` | Australian Government guidance on the use of AI in the public service |
| `Figure WP5 Ethics and governance checklist.png` | The ethics and governance checklist figure used in the report |

### WP5.2 report

Co-authored by Dr Bernadette Hyland-Wood, A/Prof Michael Guihot and
D/Prof Kerrie Mengersen (QUT). The report reviews data and AI governance frameworks
published between 2022 and 2025, sets out four adoption challenges (recommendations
are prolific but fragmented, general-purpose frameworks do not address
domain-specific needs, responsibility is diffused and accountability unclear, and
implementation pathways are missing), and makes six recommendations to the ARDC
Advanced Analytics and AI Resource Hub.

### Ethics and governance matrix

Authored by A/Prof Michael Guihot (QUT Law School) and Dr Bernadette Hyland-Wood
(QUT Centre for Data Science). The matrix catalogues **41 instruments** ranked by
relevance to health researchers and clinicians, arranged in four tiers:

| Tier | Scope | Entries |
|------|-------|---------|
| Tier 1 | Core research ethics and health data access | 17 |
| Tier 2 | Clinical AI, translation and liability | 9 |
| Tier 3 | AI governance frameworks and policy direction | 9 |
| Tier 4 | Adjacent and situational | 6 |

Each entry records eight fields: resource, status (whether the instrument binds),
licensing, who it applies to, lifecycle stage, why it matters, currency, and
constraints and watch points. The matrix distinguishes **constraints**, which mean
you must comply and which come from legislation, regulatory instruments or
institutional policy, from **watch points**, which are emerging or context-dependent
considerations you should assess for your own project.

The licensing column uses a four-way key:

- **(a)** open and freely reusable
- **(b)** open with attribution requirements
- **(c)** requires permission or negotiation
- **(d)** paid or otherwise restricted

Most entries are (b), typically CC BY 4.0. Entries you should check before reusing
include the ACSQHC materials (CC BY-NC-ND 4.0, exact copies only), AIATSIS and
AHPRA resources (permission needed beyond fair dealing), some professional college
standards (member-gated), and ISO/IEC 42001 (purchase required).

## Reference library

`Literature Guides Frameworks/` holds the source material behind the deliverables.
It is organised into three groups:

- **Frameworks and guides** (17 files) covering the AIHW Data Governance Framework
  and Five Safes, the Australian Government assurance and automated decision-making
  guidance, Australia's AI Ethics Principles, the Voluntary AI Safety Standard
  guardrails, OAIC privacy checklists, the NHMRC guide for assessing research
  involving AI, the NIST AI Risk Management Framework and the EU Data Toolkit.
- **National AI Centre guides** (15 files) including the AI policy guide and
  template, the AI register template (`.docx` and `.xlsx`), a business process
  mapping template, a team readiness canvas, a data quality checklist, questions to
  ask AI suppliers, and three facilitated workshop scenario decks.
- **Department of Industry guide and template** (2 files) containing the 2025 AI
  policy template.

Four peer-reviewed articles sit alongside them (Gorelik et al. 2025, Lekadir et al.
2025 on FUTURE-AI, Topol 2019, and Wen et al. 2025), making 21 files at the top level
of `Literature Guides Frameworks/`.

### Reusable templates

If you want something you can pick up and apply rather than read, start with these:

- `National AI Centre Guides/National AI Centre AI-register-template.xlsx`
- `National AI Centre Guides/National AI Centre AI-policy-guide-and-template.docx`
- `National AI Centre Guides/National AI Centre Business-process-mapping-template.docx`
- `National AI Centre Guides/National AI Centre team-readiness-canvas.pdf`
- `Dept of Industry Guide and Template/TEMPLATE AI Policy.docx`

## Access

Everything in WP5 is publicly readable. The repository is public, no files use Git
LFS, and every file downloads directly over HTTPS.

To retrieve a single file without cloning the whole repository (which is
approximately 537 MB):

```bash
curl -L -O "https://raw.githubusercontent.com/gnanabharathy/AAAIR/main/WP5/05%20Ethics%20%26%20Governance%20(WP%205)/WP5%20Deliverables/WP5.2%20Ethics%20and%20Governance%20SUBMITTED%20v1.0.pdf"
```

To check out WP5 alone:

```bash
git clone --filter=blob:none --sparse https://github.com/gnanabharathy/AAAIR.git
cd AAAIR
git sparse-checkout set WP5
```

Note that directory names contain spaces, ampersands and parentheses. Quote paths in
shell commands and percent-encode them in URLs.

### Licensing

The repository carries an MIT licence, which covers the project's own outputs. The
third-party PDFs, templates and framework documents in
`Literature Guides Frameworks/` retain the licences of their originating
institutions, which the matrix documents per item. The MIT licence at the repository
root does not override those terms.

Redistribution of some of this third-party material, particularly the ACSQHC
(CC BY-NC-ND), AIATSIS and AHPRA items, may need review before the hub is published
more widely. Please raise this with the ARDC legal or policy contact rather than
treating the repository licence as settling the question. This README does not
constitute legal advice.

### Link currency

The matrix carries 59 unique external hyperlinks. As at 28 September 2026, 54
resolve normally. One is broken and needs correction:

- `https://www.safetyandquality.gov.au/using-website/disclaimer-and-copyright` returns 404

Three others (NSW legislation, the AHRC *Human Rights and Technology* summary PDF,
and EUR-Lex) block automated checking but are expected to open in a browser.

## Known gaps

- There is no machine-readable version of the matrix. It exists only as `.docx` and
  `.pdf`. A CSV or JSON export would let WP6 and WP7 consume it programmatically.
- The matrix states its position as at 15 June 2026 and several entries note
  anticipated revision schedules. It will need a currency review before reuse.
- No WP5.1, WP5.3 or later sub-package deliverables appear in this folder. Only
  WP5.2 is present.

## Maintenance

Update the matrix version and the "position as of" date together whenever entries
change. When you add an instrument, complete all eight columns, including licensing
and currency, so that downstream users can judge both applicability and reuse
rights.

---

Part of the [AAAIR](../README.md) project (ARDC-ADSN Advanced Analytics and AI
Resource Hub). See the root README for the full work package structure.
