# zotero-paper-import

[English](README.md) | [简体中文](README.zh-CN.md)

An agent skill for finding papers, downloading PDFs and preparing native Zotero imports. Supports DOI, arXiv (including explicit versions), URLs and title searches. Optional paper summaries support OrcaRouter, OpenAI and custom OpenAI-compatible HTTPS providers.

## Install

```bash
git clone https://github.com/FidollarinLA/zotero-paper-import.git ~/.cursor/skills/zotero-paper-import
```

For other skill-enabled agents, place this repository in their supported skills directory. Requires Python 3.10+, curl and local Zotero. Copy `config.example.md` to gitignored `config.md` for agent preferences; scripts take explicit CLI arguments.

## Import workflow

```bash
python3 scripts/resolve_paper.py --arxiv 2602.03070v5
python3 scripts/download_pdf.py --arxiv 2602.03070v5 --preference any --output ./paper.pdf
python3 scripts/import_to_zotero.py --arxiv 2602.03070v5 --pdf ./paper.pdf --collection "My Papers" --output ./papers.ris --receipt ./preparation.json
```

Then in Zotero: **File → Import → A file**, select `papers.ris`, copy attachments and add the imported items to the intended collection. Check item count, metadata and opening PDFs. Zotero can remain open throughout. The script only prepares RIS, checks duplicates read only and reports per-paper status/hashes; it does not modify the database, import items or create collections.

DOIs use Crossref; arXiv metadata uses the arXiv API. Network services may be unavailable; verified metadata can be supplied offline in a manifest ([examples](examples.md)). A preprint's journal DOI is kept separate. Unpaywall is optional and needs `--email` with your real contact email. Published-only mode rejects accepted manuscripts/preprints; ask for a legitimately obtained PDF when necessary.

## Optional OrcaRouter integration

Create an [OrcaRouter account/API key](https://docs.orcarouter.ai/quickstart). Select an exact model ID from its current catalog and put `ORCAROUTER_API_KEY` in your local environment. Never commit keys. The fixed endpoint is `https://api.orcarouter.ai/v1`.

```bash
python3 scripts/summarize_paper.py --provider orcarouter --model "<catalog-model-id>" --input ./abstract.txt --output ./summary.md
```

This previews locally without a key or request. Add `--send` only to transmit the selected text and accept potential usage fees. No automatic upload, retry or paid fallback. Other providers: `--provider openai` with `OPENAI_API_KEY`, or `--provider custom --base-url https://your-provider.example/v1` with `LLM_API_KEY`. Basic import works independently of these services. Summaries must be checked against the paper.

Maintainers can apply to the [Built with OrcaRouter program](https://www.orcarouter.ai/zh-CN/built-with). Partner approval and the project's dedicated referral link are separate from API setup. No project referral link has been configured yet; this integration alone does not enable attributed revenue sharing.

## Upgrade notes

The original importer wrote SQLite directly. It now generates RIS; finish via Zotero's native importer. `replace` is no longer accepted; use native merge/edit for existing items. `skip` checks normalized identifiers across the batch and local libraries, excludes trashed items and treats arXiv versions as one paper; it cannot identify records without identifiers or automatically associate journal/preprint versions. `new_copy` permits an intentional duplicate. A missing database means batch-only checks; an unreadable existing database stops preparation. Review group-library matches before skipping a personal-library import. Collection paths are preparation hints and must be selected in Zotero. If a batch has no prepared records, `ris` is null and any existing output is left unchanged: do not import that stale file.

## Validation and scope

```bash
python3 -m unittest discover -s tests -v
```

CI runs on Python 3.10 and 3.13. Tests cover identifiers/versions, published PDF selection, native RIS, read-only duplicate handling, partial failure and optional provider requests. API tests are mocked; they do not prove live billing or partner attribution. Scope: articles/conference papers/preprints; books and theses are not covered. PDF signature validation rejects obvious HTML, not every corrupt PDF. Original workflow images under `assets/` describe the older release.

[Agent instructions](SKILL.md) · [Examples](examples.md) · [References](reference.md) · [MIT license](LICENSE)
