# References and behavior

- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/): DOI and title metadata.
- [arXiv API](https://info.arxiv.org/help/api/index.html): versioned preprint metadata. Stable arXiv DOI supports duplicate matching; a later journal DOI is a separate field.
- [Unpaywall API](https://unpaywall.org/products/api): supply a real email; publishedVersion differs from acceptedVersion/submittedVersion. Without an email this lookup is skipped.
- [Zotero importing](https://www.zotero.org/support/adding_items_to_zotero): native file import.
- [Zotero RIS translator](https://github.com/zotero/translators/blob/master/RIS.js): L1 imports PDF attachments. Local paths avoid an additional remote download. RIS RPRT represents an arXiv preprint as a report with Preprint type and a version note; it is not Zotero's dedicated preprint item type. Review native field mappings after import.
- [OrcaRouter introduction](https://docs.orcarouter.ai/introduction): OpenAI-compatible endpoint `https://api.orcarouter.ai/v1`.
- [Built with OrcaRouter](https://www.orcarouter.ai/zh-CN/built-with): partner application, separate from model/API access.

The downloader tries Nature reference/direct URLs and an Unpaywall PDF when available; direct arXiv requests use arXiv PDF URLs. It does not support every publisher or bypass access controls. `%PDF-` signature checking is an initial screen; opening the final PDF remains necessary.

## Optional provider setup

Create your own account and API key; select the exact model ID from the current provider catalog. Store the key only in your local environment. `summarize_paper.py` sends OpenAI-compatible `POST /chat/completions` with bearer authentication, messages and a token cap. Its default is local preview. `--send` transmits only the text file you explicitly selected; fees depend on that model and account. No automatic retries or paid fallback. Mock tests verify request format, not live service availability.

OrcaRouter is one optional provider alongside OpenAI/custom endpoints. There is no forced branding, exclusive provider or automatic default. Approval and a dedicated project referral link are needed for partner attribution. The repository currently has no such link, so revenue sharing cannot yet be claimed. Add the verified link after approval, then independently verify attribution in the partner dashboard. Program terms govern eligibility, payout and continuation after exit.
