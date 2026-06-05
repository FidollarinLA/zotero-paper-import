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


def curl_download(url: str, output: Path) -> int:
    result = subprocess.run(
        ["curl", "-fsSL", "-o", str(output), "-w", "%{http_code}", url],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0
    return int(result.stdout.strip() or "0")


def is_pdf(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        return False
    result = subprocess.run(["file", "-b", str(path)], capture_output=True, text=True)
    return "PDF document" in result.stdout


def doi_to_nature_slug(doi: str) -> str | None:
    if not doi.startswith("10.1038/"):
        return None
    return "s" + doi.split("/", 1)[1]


def unpaywall_pdf(doi: str, email: str) -> str | None:
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}?email={quote(email)}"
    result = subprocess.run(["curl", "-fsSL", url], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    loc = data.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or loc.get("url")


def arxiv_from_doi(doi: str) -> str | None:
    if doi.startswith("10.48550/arXiv."):
        arxiv_id = doi.split("arXiv.", 1)[1]
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    return None


def candidate_urls(doi: str, email: str) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    slug = doi_to_nature_slug(doi)
    if slug:
        urls.append(("nature_reference", f"https://www.nature.com/articles/{slug}_reference.pdf"))
        urls.append(("nature_direct", f"https://www.nature.com/articles/{slug}.pdf"))

    oa = unpaywall_pdf(doi, email)
    if oa:
        urls.append(("unpaywall", oa))

    arxiv = arxiv_from_doi(doi)
    if arxiv:
        urls.append(("arxiv", arxiv))

    return urls


def main() -> None:
    parser = argparse.ArgumentParser(description="Download paper PDF")
    parser.add_argument("--doi", required=True)
    parser.add_argument("--output", required=True, help="Output PDF path")
    parser.add_argument("--preference", choices=["published", "any"], default="published")
    parser.add_argument("--email", default="openaccess@example.com", help="Email for Unpaywall API")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    published_sources = {"nature_reference", "nature_direct", "unpaywall"}
    tried = []

    for source, url in candidate_urls(args.doi, args.email):
        if args.preference == "published" and source not in published_sources:
            continue

        tmp = output.with_suffix(".tmp")
        if tmp.exists():
            tmp.unlink()

        code = curl_download(url, tmp)
        tried.append({"source": source, "url": url, "http_code": code, "is_pdf": is_pdf(tmp)})

        if is_pdf(tmp):
            tmp.replace(output)
            print(json.dumps({"status": "ok", "source": source, "path": str(output), "tried": tried}, indent=2))
            return

        if tmp.exists():
            tmp.unlink()

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
