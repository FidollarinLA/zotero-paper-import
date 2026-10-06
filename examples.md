# Examples

Run from the repository or installed skill root. On Windows replace `python3` with `py -3`; forward slashes in the examples also work in PowerShell. PDFs must remain accessible until Zotero copies the attachments.

## DOI: published PDF

```bash
python3 scripts/resolve_paper.py --doi 10.1038/s41586-026-10644-y
python3 scripts/download_pdf.py --doi 10.1038/s41586-026-10644-y --output ./paper.pdf --preference published
python3 scripts/import_to_zotero.py --doi 10.1038/s41586-026-10644-y --pdf ./paper.pdf --output ./papers.ris --receipt ./preparation.json --collection "My Papers"
```

If download fails, supply a legitimately obtained PDF; do not treat an HTML paywall as success. Finish with native Zotero import, copy attachments, choose the collection and verify.

## Batch with offline metadata

Save `batch.json` (paths are illustrative; use actual absolute paths):

```json
[
  {
    "pdf": "/path/to/paper.pdf",
    "metadata": {
      "doi": "10.48550/arXiv.2602.03070",
      "arxiv_id": "2602.03070v5",
      "title": "Verified paper title",
      "authors": [{"given": "Jane", "family": "Doe"}],
      "date": "2026-02-03",
      "journal": "arXiv",
      "url": "https://arxiv.org/abs/2602.03070v5",
      "source": "arxiv",
      "abstract": "Verified abstract."
    }
  }
]
```

```bash
python3 scripts/import_to_zotero.py --manifest batch.json --collection "Parent/Child" --output ./papers.ris --receipt ./preparation.json
```

Without `metadata`, each entry needs `doi`, `arxiv` or `url` plus `pdf`; metadata will be resolved online. Relative PDF paths are resolved from the manifest's directory. Windows paths can use forward slashes, for example `C:/Users/your-name/Downloads/paper.pdf`; UTF-8 JSON with a BOM is accepted. Review each prepared/skipped/failed result; only prepared entries appear in the new RIS. `--duplicate-policy new_copy` permits another copy when explicitly intended. Preparation does not create nested collections.

## Optional summary

Put only the selected abstract/excerpt in UTF-8 `abstract.txt`. Use the [project signup link](https://www.orcarouter.ai/ref/ref_e92ed6bbb348dc9b078b) if you need an OrcaRouter account. Set `ORCA_KEY` or `ORCAROUTER_API_KEY` locally. Preview with the configured `orcarouter/auto` model (potentially paid when sent):

```bash
python3 scripts/summarize_paper.py --provider orcarouter --input abstract.txt --output summary.md
```

Preview sends nothing. After authorizing transmission and potential cost, append `--send`. This does not import the summary into Zotero automatically. Keep AI text separate from verified paper metadata.

Use `--model "<catalog-model-id>"` for a specific current model. `python3 scripts/doctor.py --check-provider` checks catalog access without an inference request. On macOS/Linux, set a session key with `read -r -s ORCA_KEY; export ORCA_KEY`. On Windows, use the secure PowerShell prompt in [README.zh-CN.md](README.zh-CN.md).
