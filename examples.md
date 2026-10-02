# Examples

Run from the repository root. PDFs and RIS files must remain accessible until Zotero copies the attachments.

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

Without `metadata`, each entry needs `doi`, `arxiv` or `url` plus `pdf`; metadata will be resolved online. Paths are resolved from the working directory. Review each prepared/skipped/failed result; only prepared entries appear in the new RIS. `--duplicate-policy new_copy` permits another copy when explicitly intended. Preparation does not create nested collections.

## Optional summary

Put only the selected abstract/excerpt in UTF-8 `abstract.txt`. Configure the key locally and choose a real current model ID:

```bash
python3 scripts/summarize_paper.py --provider orcarouter --model "<catalog-model-id>" --input abstract.txt --output summary.md
```

Preview sends nothing. After authorizing transmission and potential cost, append `--send`. This does not import the summary into Zotero automatically. Keep AI text separate from verified paper metadata.
