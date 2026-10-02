# Configuration Template

Copy to gitignored `config.md`. Agent guidance only; scripts use explicit CLI flags.

```yaml
zotero_db: ~/Zotero/zotero.sqlite
download_dir: ~/Documents/Zotero_Imports
default_collection: Imported
pdf_preference: published  # published | any
duplicate_policy: skip     # skip | new_copy
unpaywall_email: ""        # optional real contact email, not a placeholder
# Optional summary service; omitted means no LLM use.
summary_provider: ""       # orcarouter | openai | custom
summary_model: ""          # exact current catalog ID
```

Keys belong in local environment variables only: `ORCAROUTER_API_KEY`, `OPENAI_API_KEY` or `LLM_API_KEY`. `--send` requires authorization to transmit selected text and incur potential costs. Never commit private paths, contact details or keys. Native Zotero import must copy PDF attachments and be verified afterwards.
