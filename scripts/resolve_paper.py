#!/usr/bin/env python3
"""Resolve a paper identifier to structured metadata via CrossRef or Semantic Scholar."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import quote


def curl_json(url: str) -> dict:
    result = subprocess.run(
        ["curl", "-fsSL", url],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"HTTP request failed: {url}\n{result.stderr}")
    return json.loads(result.stdout)


def extract_doi_from_url(url: str) -> str | None:
    match = re.search(r"10\.\d{4,9}/[^\s?#]+", url)
    return match.group(0).rstrip(".,)") if match else None


def parse_crossref_message(msg: dict) -> dict:
    date_src = msg.get("published-print") or msg.get("published-online") or {}
    parts = date_src.get("date-parts", [[]])[0]
    year = parts[0] if parts else None
    month = parts[1] if len(parts) > 1 else None
    day = parts[2] if len(parts) > 2 else None

    authors = [
        {"given": a.get("given", ""), "family": a.get("family", "")}
        for a in msg.get("author", [])
    ]

    return {
        "doi": msg.get("DOI", ""),
        "title": (msg.get("title") or [""])[0],
        "authors": authors,
        "year": year,
        "month": month,
        "day": day,
        "journal": (msg.get("container-title") or [""])[0],
        "volume": msg.get("volume"),
        "issue": msg.get("issue"),
        "pages": msg.get("page"),
        "url": msg.get("URL", ""),
        "abstract": _strip_jats(msg.get("abstract", "")),
        "source": "crossref",
    }


def _strip_jats(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def resolve_by_doi(doi: str) -> dict:
    data = curl_json(f"https://api.crossref.org/works/{quote(doi, safe='')}")
    return parse_crossref_message(data["message"])


def resolve_by_url(url: str) -> dict:
    doi = extract_doi_from_url(url)
    if not doi:
        raise ValueError(f"Could not extract DOI from URL: {url}")
    result = resolve_by_doi(doi)
    result["url"] = url
    return result


def resolve_by_title(title: str) -> list[dict]:
    query = quote(title)
    data = curl_json(
        f"https://api.crossref.org/works?query.title={query}&rows=5&select=DOI,title,author,published-print,published-online,container-title,URL"
    )
    return [parse_crossref_message(item) for item in data["message"]["items"]]


def resolve_by_query(query: str) -> list[dict]:
    data = curl_json(
        f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(query)}&limit=5&fields=title,authors,year,externalIds,url,abstract,journal"
    )
    results = []
    for paper in data.get("data", []):
        ext = paper.get("externalIds") or {}
        doi = ext.get("DOI", "")
        authors = [
            {
                "given": " ".join((a.get("name") or "").split()[:-1]),
                "family": (a.get("name") or "").split()[-1] if a.get("name") else "",
            }
            for a in paper.get("authors", [])
        ]
        results.append(
            {
                "doi": doi,
                "title": paper.get("title", ""),
                "authors": authors,
                "year": paper.get("year"),
                "journal": (paper.get("journal") or {}).get("name", ""),
                "url": paper.get("url", ""),
                "abstract": paper.get("abstract", ""),
                "source": "semantic_scholar",
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve paper metadata")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doi")
    group.add_argument("--url")
    group.add_argument("--title")
    group.add_argument("--query")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    try:
        if args.doi:
            output = resolve_by_doi(args.doi)
        elif args.url:
            output = resolve_by_url(args.url)
        elif args.title:
            output = resolve_by_title(args.title)
        else:
            output = resolve_by_query(args.query)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
