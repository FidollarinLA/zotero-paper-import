#!/usr/bin/env python3
"""Resolve a paper identifier to structured metadata via Crossref, arXiv or Semantic Scholar."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from urllib.parse import quote
from runtime import configure_stdio


def curl_json(url: str) -> dict:
    result = subprocess.run(
        ["curl", "-fsSL", "--connect-timeout", "10", "--max-time", "45", url],
        capture_output=True,
        text=True,
        encoding='utf-8', errors='replace',
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


def arxiv_id(value: str) -> str | None:
    value = unquote(value.strip())
    value = re.sub(r"^(?:https?://(?:export\.)?arxiv\.org/(?:abs|pdf)/|https?://doi\.org/10\.48550/arxiv\.|10\.48550/arxiv\.|arxiv:)", "", value, flags=re.I)
    value = value.removesuffix(".pdf")
    return value if re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-zA-Z.-]+/\d{7})(?:v\d+)?", value) else None


def parse_arxiv_feed(xml: str, requested_id: str) -> dict:
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(xml)
    entry = root.find("a:entry", ns)
    if entry is None:
        raise ValueError("arXiv returned no matching paper")
    resolved = arxiv_id(entry.findtext("a:id", "", ns))
    if not resolved or re.sub(r"v\d+$", "", resolved) != re.sub(r"v\d+$", "", requested_id):
        raise ValueError("arXiv returned an unexpected identifier")
    if re.search(r"v\d+$", requested_id) and resolved != requested_id:
        raise ValueError("arXiv returned an unexpected version")
    published = entry.findtext("a:published", "", ns)[:10]
    authors = []
    for node in entry.findall("a:author/a:name", ns):
        parts = (node.text or "").split()
        authors.append({"given": " ".join(parts[:-1]), "family": parts[-1] if parts else ""})
    base = re.sub(r"v\d+$", "", resolved)
    return {
        "doi": "10.48550/arXiv." + base,
        "arxiv_id": resolved,
        "title": " ".join(entry.findtext("a:title", "", ns).split()),
        "authors": authors, "date": published,
        "year": int(published[:4]) if published else None,
        "month": int(published[5:7]) if published else None,
        "day": int(published[8:10]) if published else None,
        "journal": "arXiv", "item_type": "preprint",
        "url": "https://arxiv.org/abs/" + resolved,
        "pdf_url": "https://arxiv.org/pdf/" + resolved,
        "abstract": " ".join(entry.findtext("a:summary", "", ns).split()),
        "published_doi": entry.findtext("x:doi", "", ns), "source": "arxiv",
    }


def resolve_by_arxiv(identifier: str) -> dict:
    identifier = arxiv_id(identifier)
    if not identifier:
        raise ValueError("Invalid arXiv identifier")
    result = subprocess.run(
        ["curl", "-fsSL", "--connect-timeout", "10", "--max-time", "45",
         "https://export.arxiv.org/api/query?id_list=" + quote(identifier, safe="")],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=False,
    )
    if result.returncode:
        raise RuntimeError("arXiv metadata unavailable; retry later or provide a metadata manifest")
    try:
        return parse_arxiv_feed(result.stdout, identifier)
    except ET.ParseError as exc:
        raise ValueError('arXiv returned invalid metadata; retry or use a verified manifest') from exc


def resolve_by_doi(doi: str) -> dict:
    if arxiv_id(doi):
        return resolve_by_arxiv(doi)
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    data = curl_json(f"https://api.crossref.org/works/{quote(doi, safe='')}")
    return parse_crossref_message(data["message"])


def resolve_by_url(url: str) -> dict:
    if arxiv_id(url):
        return resolve_by_arxiv(url)
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
    configure_stdio()
    parser = argparse.ArgumentParser(description="Resolve paper metadata")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doi")
    group.add_argument("--arxiv")
    group.add_argument("--url")
    group.add_argument("--title")
    group.add_argument("--query")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    try:
        if args.arxiv:
            output = resolve_by_arxiv(args.arxiv)
        elif args.doi:
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
