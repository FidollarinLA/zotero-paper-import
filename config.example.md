# Configuration Template

Copy this file to `config.md` and fill in your values.  
`config.md` is listed in `.gitignore` — do not commit personal paths.

```yaml
# Zotero paths
zotero_db: ~/Zotero/zotero.sqlite
zotero_storage: ~/Zotero/storage

# Defaults
download_dir: ~/Documents/Zotero_Imports
default_collection: Imported
pdf_preference: published   # published | any
duplicate_policy: skip      # skip | replace | new_copy

# Optional: contact email for Unpaywall API (required by their ToS)
unpaywall_email: your-email@example.com
```

The agent reads `config.md` when present; otherwise it uses the defaults above.
