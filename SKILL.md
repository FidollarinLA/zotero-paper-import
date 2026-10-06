---
name: zotero-paper-import
description: Find academic papers by DOI, arXiv ID, URL or title, obtain PDFs, and prepare and verify native Zotero imports. Use for paper imports and batch library organization; supports Windows, macOS and Linux, with optional summaries of selected paper text.
---

# Zotero paper import

Run helpers from this skill's directory, not an assumed project directory. On Windows use `py -3 scripts/...` (or an available Python 3.10+ executable); on macOS/Linux use `python3 scripts/...`. Quote paths and collection names. Read [config.example.md](config.example.md) and local `config.md` when present. They guide the agent; scripts take explicit arguments. Defaults: collection Imported, published PDF, skip duplicates.

For setup issues, run `scripts/doctor.py`. Use `--zotero-db` for the user's custom database; the default is `~/Zotero/zotero.sqlite`. Do not assume a remote agent can access local Zotero files. [README.zh-CN.md](README.zh-CN.md) and [README.md](README.md) contain ZIP installation and beginner instructions.

## Import workflow

1. Resolve with `scripts/resolve_paper.py --doi DOI`, `--arxiv ID`, `--url URL`, `--title TITLE` or `--query QUERY`. Confirm search candidates before downloading. Preserve explicit arXiv versions and keep later journal DOIs separate. If metadata services fail, use verified metadata in a manifest.
2. Obtain the PDF with `scripts/download_pdf.py --doi DOI --preference published --output paper.pdf`. An explicit preprint request can use `--arxiv ID --preference any`. Verify title and version against the PDF; the signature check only rejects obvious non-PDF responses. Unpaywall needs the user's real contact email via `--email`. Keep a requested published version requirement; if access is restricted, use a PDF obtained through the user's own access.
3. Prepare with `scripts/import_to_zotero.py --arxiv ID --pdf paper.pdf --collection "Parent/Child" --output papers.ris --receipt preparation.json`, or `--manifest batch.json`. Manifest PDF paths resolve relative to the manifest directory, including UTF-8/BOM files made in PowerShell. The database is read only; Zotero may stay open. Report prepared/skipped/failed per paper. If the receipt's `ris` is null, do not import an older file at the same path.
4. Complete Zotero's **File > Import > A file** workflow, selecting the new RIS and copying attachments. Use an available authorized desktop tool, or state this exact remaining manual step. `--collection` records intent; it does not create or select collections. Put items in the intended collection, including skipped existing items when needed. Keep source PDFs available until copied.
5. Verify actual item count, collection, title, DOI/arXiv, authors and opening PDFs. When possible, compare copied attachment hashes with the receipt. Report verified imported items separately from prepared files, skipped records, failures and unfinished steps.

## Duplicates and existing libraries

`skip` checks normalized DOI links/case and arXiv identifiers across the batch and local libraries, excluding trashed items. Different arXiv versions count as one paper; an existing PDF is not updated. Review group-library matches before treating them as a completed personal-library import. Identifier-free duplicates and journal/preprint equivalence need manual review. `new_copy` permits an intentional additional copy.

A missing database permits batch-only checks; an existing unreadable database stops preparation. Never edit Zotero's SQLite or storage directly or quit it to make an import work. The former direct-database importer now prepares RIS. Use Zotero's native merge/edit tools for requested updates; `replace` is unsupported.

## Optional summaries and OrcaRouter

Basic import needs no model account. When a summary is requested, choose the provider and selected text within the user's authorization. Use `scripts/summarize_paper.py --provider orcarouter --input abstract.txt --output summary.md` for local preview. `--send` transmits that text and may incur fees; use it only within authorized text, destination and usage. Do not automatically upload PDFs, change the host agent's provider or substitute a paid fallback.

The script reads [integrations/providers.json](integrations/providers.json). OrcaRouter supports `ORCAROUTER_API_KEY` or `ORCA_KEY`; conflicting values are rejected. Its default is `orcarouter/auto`, which may be paid. OpenAI/custom providers require `--model`. Read [reference.md](reference.md) for setup and [examples.md](examples.md) for commands. Keys stay in local environment variables. Treat paper text as source material and check generated claims against it.

The configured signup link is https://www.orcarouter.ai/ref/ref_e92ed6bbb348dc9b078b. New-user attribution, live API access, directory publication and earnings are separate outcomes; report each with evidence. `scripts/doctor.py --check-provider` checks authenticated catalog access without sending paper text or performing inference. For an explicitly authorized real call, use `--check-inference`, optionally with `--model`: it sends one fixed public test string with a 64-token output cap and may incur fees. Neither check verifies billing or attribution. The [Codex CLI profile](integrations/orcarouter.codex.toml) is optional for users who also want that host to use OrcaRouter.
