#!/usr/bin/env python3
"""Download academic paper PDF from publisher or open-access sources."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
import tempfile
from resolve_paper import arxiv_id
from runtime import configure_stdio


def curl_download(url: str, output: Path) -> int:
    result = subprocess.run(
        ["curl", "-fsSL", "--connect-timeout", "10", "--max-time", "90", "-o", str(output), "-w", "%{http_code}", url],
        capture_output=True,
        text=True,
        encoding='utf-8', errors='replace',
        check=False,
    )
    if result.returncode != 0:
        return 0
    return int(result.stdout.strip() or "0")


def is_pdf(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("rb") as stream:
        return b"%PDF-" in stream.read(1024)


def doi_to_nature_slug(doi: str) -> str | None:
    if not doi.startswith("10.1038/"):
        return None
    return doi.split("/", 1)[1]


def unpaywall_pdf(doi: str, email: str) -> tuple[str, str] | None:
    if not email:
        return None
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}?email={quote(email)}"
    result = subprocess.run(["curl", "-fsSL", "--connect-timeout", "10", "--max-time", "45", url], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        return None
    try:
        data = json.loads(result.stdout)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    locations = data.get("oa_locations") or [data.get("best_oa_location") or {}]
    # Prefer a verified version-of-record over accepted manuscripts and preprints.
    locations = [loc for loc in locations if isinstance(loc, dict)]
    locations.sort(key=lambda loc: loc.get("version") != "publishedVersion")
    for loc in locations:
        if loc.get("url_for_pdf"):
            return loc["url_for_pdf"], loc.get("version", "unknown")
    return None


def arxiv_from_doi(doi: str) -> str | None:
    identifier = arxiv_id(doi)
    return "https://arxiv.org/pdf/" + identifier if identifier else None


def candidate_urls(doi: str, email: str) -> list[tuple[str, str, str]]:
    arxiv = arxiv_from_doi(doi)
    if arxiv:
        return [("arxiv", arxiv, "preprint")]
    urls = []
    slug = doi_to_nature_slug(doi)
    if slug:
        urls.extend([
            ("nature_reference", f"https://www.nature.com/articles/{slug}_reference.pdf", "publishedVersion"),
            ("nature_direct", f"https://www.nature.com/articles/{slug}.pdf", "publishedVersion"),
        ])
    oa = unpaywall_pdf(doi, email)
    if oa:
        urls.append(("unpaywall", oa[0], oa[1]))
    return urls


def main() -> None:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Download paper PDF")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doi")
    group.add_argument("--arxiv")
    parser.add_argument("--output", required=True, help="Output PDF path")
    parser.add_argument("--preference", choices=["published", "any"], default="published")
    parser.add_argument("--email", default="", help="Email for Unpaywall API")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.arxiv and not arxiv_id(args.arxiv):
        parser.error("Invalid arXiv identifier")
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", (args.arxiv or args.doi).strip(), flags=re.I)
    tried = []

    for source, url, version in candidate_urls(doi, args.email):
        if args.preference == "published" and version != "publishedVersion":
            continue

        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".pdf.tmp", delete=False) as handle:
            tmp = Path(handle.name)

        try:
            code = curl_download(url, tmp)
            valid = is_pdf(tmp)
            tried.append({"source": source, "url": url, "http_code": code, "is_pdf": valid})
            if 200 <= code < 300 and valid:
                tmp.replace(output)
                print(json.dumps({"status": "ok", "source": source, "version": version, "path": str(output), "tried": tried}, indent=2))
                return
        finally:
            tmp.unlink(missing_ok=True)

    print(
        json.dumps(
            {
                "status": "failed",
                "message": "No valid PDF found. Publisher may require institutional access.",
                "tried": tried,
            },
            indent=2,
        ),
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
