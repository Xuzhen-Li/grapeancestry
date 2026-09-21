# Grok Bot worker cards — Xuzhen-Li/grapeancestry

Lead: GitHub bot merges. Workers return ①必改 / ②建议 (or draft text). Do not invent paper results. Do not commit banned assets.

## Shared facts

(see also repo README / DATA_NOTICE.md)

- Product: local Docker app, grapevine 167K on VS-1; image `grapeancestry:1.0.0`; tar `grapeancestry-v1.0.0-amd64.tar` from `Zenodo Restricted record — DOI after publish`.
- Public git = code + docs + Ages HTML. No VS-1 / 2449 / tar in git. Never docker push fat image. Never public Release for tar.
- UI 8501 + reports 8502. Setup auth scrypt in `./settings/auth.json`. Sidebar Analysis / Demos / Settings.
- Product file: `*.sample-first-v2.report.html`. `chip.json` optional only.
- BAM must be VS-1 numeric contigs. ENA ERR16654874 BAM is 12Xv2 download-demo only.
- Author 李旭真 / Li Xuzhen · ORCID 0000-0003-3670-6657. MIT = code only.
- Ban tone: Tonight / 今晚 / classroom night / conda env ga / grapeancestry_suite-as-this-repo.
- Three paths: Docker kit · Demo on GitHub · DIY `docs/steps/00a–13b`.

## W1 — README lead (LAST)

Rewrite/keep README: project intro; honest three-path table; Docker from-scratch with `Zenodo Restricted record — DOI after publish`; **screenshot gallery** using `docs/guideline_shots/panels/*.png` (do not delete shots); link USER_GUIDE, GUIDELINE, steps; DIY first-class; author line. No Tonight. Lead merges after W3/W4/W6 exist.

## W2 — USER_GUIDE product path

From-scratch deploy: download tar → load → start.sh → Setup → Analysis/Demos → V2 on 8502. Intake, BAM rule, knobs = existing flags only. Demote chip.json.

## W3 — DATA_NOTICE + bans

Ensure `DATA_NOTICE.md` exists; `.gitignore` blocks tar/caches; Dockerfile/compose comments say never push.

## W4 — DIY steps 00a–13b

Fill `docs/steps/` from real `src/` / Snakefile / PIPELINE. Index as no-kit workflow. 14* optional.

## W5 — GUIDELINE keep shots

Keep all guideline screenshots. Strip Tonight tone only. Do not rewrite science tables.

## W6 — Launchers (FIRST)

`start.sh` / `start.command` / `start.bat`: mkdir input/output/settings; load tar or honest build note; ports 8501/8502; Colima DOCKER_HOST; never push.

## W7 — Docker docs comments (FIRST)

Dockerfile + compose: tag 1.0.0, mounts, 8502, never push, docs-only build incomplete.

## W8 — Command旁白 / SCRIPTS map

Public clone: Ages `http.server` works. Kit needs tar. DIY needs private assets. Align `docs/SCRIPTS.md` entry with three paths.

## Gemini (after W1+W3)

Optional: flowchart PNG claim labels (OIV225 solid vs do-not-claim). One prompt at a time on gemini.google.com.

## Gemini Pass A / B (second brain)

- **Pass A (first):** one gemini.google.com prompt → markdown drafts only (Captions / First-hour+FAQ / DIY spine / Glossary). Fact fence: src + Snakefile + PIPELINE/SCRIPTS/steps + two DOIs only.
- Lead forwards: captions → W1+W3 · first-hour/FAQ → W2 · DIY spine → W4+W5 · glossary → W8. Delete any command/paper detail not in fence.
- Workers land `docs/FAQ.md` and `docs/GLOSSARY.md` after fact-check.
- **Pass B:** page review after push (Lead kicks separately).
- Kick Pass A **in parallel with W6+W7**.
