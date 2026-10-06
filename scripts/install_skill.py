#!/usr/bin/env python3
"""Install this local skill into an agent directory; works from an extracted ZIP."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from runtime import configure_stdio

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIRS = {'cursor': '.cursor', 'codex': '.agents', 'claude': '.claude'}
ROOT_FILES = ('SKILL.md', 'README.md', 'README.zh-CN.md', 'LICENSE',
              'config.example.md', 'examples.md', 'reference.md')


def install(source: Path, destination: Path, update: bool = False) -> dict:
    source, destination = source.resolve(), destination.expanduser().resolve()
    if destination == source or source in destination.parents or destination in source.parents:
        raise ValueError('Choose an installation directory separate from the source repository')
    if destination.exists() and any(destination.iterdir()):
        if not update:
            raise ValueError('Destination is not empty. Use --update to refresh an existing zotero-paper-import installation')
        manifest = destination / 'SKILL.md'
        if not manifest.is_file() or '\nname: zotero-paper-import\n' not in manifest.read_text(encoding='utf-8'):
            raise ValueError('--update requires an existing zotero-paper-import installation')
    files = [source / name for name in ROOT_FILES]
    for folder in ('scripts', 'integrations', 'assets'):
        files.extend(path for path in (source / folder).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
    if any(not file.is_file() for file in files):
        raise ValueError('Source package is incomplete; extract the full repository ZIP')
    for file in files:
        target = destination / file.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
    return {'status': 'installed', 'destination': str(destination), 'file_count': len(files),
            'next_step': 'Reload the agent skills or start a new chat, then ask to use zotero-paper-import. Local config.md is preserved.'}


def main() -> None:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--agent', choices=list(AGENT_DIRS))
    group.add_argument('--dest', type=Path, help='Custom skill directory including zotero-paper-import')
    parser.add_argument('--update', action='store_true', help='Refresh shipped files, preserving config.md and other local files')
    args = parser.parse_args()
    destination = args.dest or Path.home() / AGENT_DIRS[args.agent] / 'skills' / 'zotero-paper-import'
    try:
        print(json.dumps(install(ROOT, destination, args.update), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
