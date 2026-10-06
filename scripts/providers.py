"""Read the shipped provider configuration without reading or storing secrets."""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'integrations' / 'providers.json'
PROVIDER_CONFIG = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def provider_key(name: str) -> str:
    config = PROVIDER_CONFIG[name]
    names = [config['api_key_env'], *config.get('api_key_env_aliases', [])]
    values = [os.environ.get(env, '').strip() for env in names]
    supplied = {value for value in values if value}
    if len(supplied) > 1:
        raise ValueError('Conflicting provider keys: set only one key or use the same value for both environment variables')
    return next(iter(supplied), '')
