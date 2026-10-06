#!/usr/bin/env python3
"""Check local prerequisites; explicitly opt in to OrcaRouter catalog or inference checks."""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import sqlite3
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from import_to_zotero import library_identifiers
from providers import PROVIDER_CONFIG, provider_key
from runtime import configure_stdio


def check_environment(db: Path) -> dict:
    config = PROVIDER_CONFIG['orcarouter']
    curl = shutil.which('curl')
    report = {
        'platform': platform.system(), 'python': platform.python_version(),
        'python_supported': sys.version_info >= (3, 10), 'curl_available': bool(curl),
        'zotero_db': str(db), 'library_checked': False,
        'orcarouter': {
            'provider_config': 'integrations/providers.json',
            'base_url': config['base_url'], 'default_model': config['default_model'],
            'referral_url': config['referral_url'], 'api_key_configured': False,
            'live_access': 'not_checked',
        },
        'notes': [],
    }
    try:
        report['orcarouter']['api_key_configured'] = bool(provider_key('orcarouter'))
    except ValueError as exc:
        report['notes'].append(str(exc))
        report['orcarouter']['key_conflict'] = True
    if db.exists():
        try:
            report['known_identifiers'] = len(library_identifiers(db))
            report['library_checked'] = True
        except (OSError, ValueError, sqlite3.Error):
            report['library_error'] = True
            report['notes'].append('Existing Zotero database could not be read. Check --zotero-db before preparing an import.')
    else:
        report['notes'].append('Zotero database not found at this path. Imports can be prepared with batch-only duplicate checks; use --zotero-db for a custom data directory.')
    report['notes'].append('Finish and verify the native import in Zotero. This check does not import items or confirm public directory publication.')
    report['status'] = 'ready' if report['python_supported'] and curl else 'missing_dependency'
    if report['status'] == 'ready' and report.get('library_error'):
        report['status'] = 'library_unreadable'
    return report


def check_catalog(key: str, base_url: str) -> dict:
    request = Request(base_url.rstrip('/') + '/models', headers={'Authorization': 'Bearer ' + key})
    with urlopen(request, timeout=20) as response:
        data = json.load(response)
    models = data.get('data')
    if not isinstance(models, list):
        raise ValueError('Model catalog returned an unexpected response')
    return {'live_access': 'catalog_accessible', 'model_count': len(models),
            'inference_tested': False, 'billing_tested': False, 'attribution_tested': False}


def check_inference(key: str, base_url: str, model: str) -> dict:
    """Make one bounded request with a fixed public test string, never paper text."""
    payload = {'model': model, 'max_tokens': 64, 'messages': [
        {'role': 'user', 'content': 'Connectivity test. Reply with the single word ORCA_OK.'},
    ]}
    request = Request(base_url.rstrip('/') + '/chat/completions',
                      data=json.dumps(payload).encode('utf-8'), method='POST',
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urlopen(request, timeout=45) as response:
        data = json.load(response)
    try:
        message = data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise ValueError('Inference returned an unexpected response') from None
    if not isinstance(message, str) or not message.strip():
        raise ValueError('Inference returned no text; check the selected model and output limit')
    return {'live_access': 'inference_accessible', 'inference_tested': True,
            'requested_model': model, 'returned_model': data.get('model', model),
            'expected_reply': message.strip() == 'ORCA_OK', 'usage': data.get('usage'),
            'billing_tested': False, 'attribution_tested': False}


def main() -> None:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zotero-db', type=Path, default=Path.home() / 'Zotero' / 'zotero.sqlite')
    parser.add_argument('--check-provider', action='store_true', help='GET the model catalog with your local key; sends no paper text and makes no inference request')
    parser.add_argument('--check-inference', action='store_true', help='Make one real model call using a fixed public connectivity test; may incur fees, sends no paper text')
    parser.add_argument('--model', help='Model ID for --check-inference; defaults to orcarouter/auto')
    args = parser.parse_args()
    if args.model and not args.check_inference:
        parser.error('--model requires --check-inference')
    report = check_environment(args.zotero_db.expanduser().resolve())
    if args.check_provider or args.check_inference:
        try:
            key = provider_key('orcarouter')
            if not key:
                raise ValueError('Set ORCAROUTER_API_KEY or ORCA_KEY locally before a live provider check')
            report['orcarouter'].update(check_catalog(key, PROVIDER_CONFIG['orcarouter']['base_url']))
            if args.check_inference:
                model = args.model or PROVIDER_CONFIG['orcarouter']['default_model']
                report['orcarouter'].update(check_inference(key, PROVIDER_CONFIG['orcarouter']['base_url'], model))
        except HTTPError as exc:
            report['orcarouter']['live_access'] = 'failed'
            report['notes'].append(f'Provider HTTP {exc.code}; check credentials, workspace access and connectivity.')
        except (OSError, URLError, ValueError, TypeError) as exc:
            report['orcarouter']['live_access'] = 'failed'
            report['notes'].append(str(exc) if isinstance(exc, ValueError) else 'Provider request failed; check connectivity.')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report['status'] != 'ready' or report['orcarouter']['live_access'] == 'failed' or report['orcarouter'].get('key_conflict'):
        sys.exit(1)


if __name__ == '__main__':
    main()
