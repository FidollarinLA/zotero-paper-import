# References and behavior

- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/): DOI and title metadata.
- [arXiv API](https://info.arxiv.org/help/api/index.html): versioned preprint metadata. Stable arXiv DOI supports duplicate matching; a later journal DOI is a separate field.
- [Unpaywall API](https://unpaywall.org/products/api): supply a real email; publishedVersion differs from acceptedVersion/submittedVersion. Without an email this lookup is skipped.
- [Zotero importing](https://www.zotero.org/support/adding_items_to_zotero): native file import.
- [Zotero RIS translator](https://github.com/zotero/translators/blob/master/RIS.js): L1 imports PDF attachments. Local paths avoid an additional remote download. RIS RPRT represents an arXiv preprint as a report with Preprint type and a version note; it is not Zotero's dedicated preprint item type. Review native field mappings after import.
- [OrcaRouter introduction](https://docs.orcarouter.ai/introduction): OpenAI-compatible endpoint `https://api.orcarouter.ai/v1`.
- [Built with OrcaRouter](https://www.orcarouter.ai/built-with): provider configuration, signup attribution and public project listings.
- [Project signup link](https://www.orcarouter.ai/ref/ref_e92ed6bbb348dc9b078b): the maintainer's supplied referral link for new registrations.
- [OrcaRouter quickstart](https://docs.orcarouter.ai/getting-started/quickstart): account, key and first request.
- [OrcaRouter PKCE](https://docs.orcarouter.ai/getting-started/sign-in-with-orcarouter): for applications that obtain keys on a user's behalf. This file-based skill uses user-supplied environment keys; it does not implement an OAuth client.
- [Codex skill directories](https://learn.chatgpt.com/docs/build-skills): user skills under `~/.agents/skills`.
- [Cursor skill directories](https://cursor.com/docs/skills): user skills under `~/.cursor/skills` or `~/.agents/skills`.
- [Codex provider configuration](https://learn.chatgpt.com/docs/config-file/config-reference): optional named profile in `integrations/orcarouter.codex.toml`.
- [Zotero data directory](https://www.zotero.org/support/zotero_data): the default directory and how to find a custom one.

The downloader tries Nature reference/direct URLs and an Unpaywall PDF when available; direct arXiv requests use arXiv PDF URLs. It does not support every publisher or bypass access controls. `%PDF-` signature checking is an initial screen; opening the final PDF remains necessary.

## Optional provider setup

The summary script reads `integrations/providers.json`. OrcaRouter's endpoint is `https://api.orcarouter.ai/v1`; its default is `orcarouter/auto` (potentially paid). Set `ORCAROUTER_API_KEY` or the partner guide's `ORCA_KEY` locally. If both are set, their values must agree. OpenAI uses `OPENAI_API_KEY`; a custom HTTPS endpoint uses `LLM_API_KEY`. Explicit model IDs are available via `--model` and required for OpenAI/custom providers.

`summarize_paper.py` sends OpenAI-compatible `POST /chat/completions` with bearer authentication, messages and a token cap. Its default is local preview. `--send` transmits only the selected UTF-8 text file; UTF-8 BOM input from Windows PowerShell is accepted. Fees depend on the model and account. No automatic retries or paid fallback. `doctor.py --check-provider` uses authenticated `GET /models`, not inference. `doctor.py --check-inference` additionally makes one real chat completion with a fixed public test string and a 64-token cap, potentially incurring fees. It checks for a non-empty response and reports model/usage without echoing credentials or the generated text. Mock tests verify request behavior, not live service availability, billing or attribution.

The project referral link is configured in both READMEs and the provider JSON. OrcaRouter attributes new accounts registered through that link according to its partner rules. Existing-account app attribution requires a verified application identity; this skill does not claim to have one. Public directory publication is a separate manual step. Check actual referrals and earnings in the partner dashboard before reporting them. Configured API support, a local key, successful model calls and credited revenue each need their own evidence.

The optional TOML example adds a Codex CLI provider plus a named `orcarouter` profile. It uses the Responses wire API and `ORCA_KEY`; the standalone summary helper uses Chat Completions. Merge the example into existing host configuration only when the user wants that change. Skill installation does not edit model settings.

## Windows and batch files

Python 3.10+ and curl are required; there are no pip dependencies. Helpers print UTF-8, explicitly decode network metadata as UTF-8, and close SQLite handles after each read. Local manifest paths resolve from the manifest's directory. RIS attachments use absolute local paths, including spaces and Chinese characters. A signature check cannot prove PDF integrity or a successful Zotero import.
