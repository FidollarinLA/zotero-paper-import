# Usage Examples

## Example 1: Single paper by DOI

**User says:**

> Import DOI 10.1038/s41586-026-10644-y into Zotero, collection "AI for science"

**Agent does:**

1. `resolve_paper.py --doi 10.1038/s41586-026-10644-y`
2. `download_pdf.py --doi ... --output ~/Documents/Zotero_Imports/AI_for_science/Co-Scientist.pdf`
3. Quit Zotero
4. `import_to_zotero.py --doi ... --pdf ... --collection "AI for science"`
5. Reopen Zotero, report paths

---

## Example 2: Paper by title

**User says:**

> Find the Robin multi-agent scientific discovery paper and add it to Zotero

**Agent does:**

1. `resolve_paper.py --query "Robin multi-agent automating scientific discovery Nature 2026"`
2. Confirm match with user if multiple results
3. Download + import as above

---

## Example 3: Batch import

**User says:**

> Import these three Nature AI scientist papers into folder "AI for science"

**Agent does:**

1. Resolve each DOI
2. Download each PDF to the collection folder
3. Build `batch.json` manifest
4. `import_to_zotero.py --manifest batch.json --collection "AI for science"`

---

## Example 4: User provides PDF manually

**User says:**

> I downloaded the PDF to ~/Downloads/paper.pdf  import it, DOI is 10.1145/12345

**Agent does:**

1. Verify `file ~/Downloads/paper.pdf` is a PDF
2. Skip download step
3. `import_to_zotero.py --doi 10.1145/12345 --pdf ~/Downloads/paper.pdf --collection Imported`

---

## Example 5: Paywall — ask user

**User says:**

> I need the published version, not arXiv

**Agent does:**

1. Try publisher PDF sources
2. If only HTML returned, ask:
   - "The publisher PDF is behind a paywall. Would you like to (1) log in with your own account and download it, or (2) download it yourself and give me the file path?"
3. Wait for user response; do not silently fall back to preprint

---

## Example 6: Why quit Zotero?

**User says:**

> Why do I need to close Zotero?

**Agent explains:**

> The import script writes directly to your local Zotero database (`~/Zotero/zotero.sqlite`). Zotero locks this file while it is running. Please quit Zotero, then I will import the paper and attach the PDF. After that, you can reopen Zotero to see the new items.
