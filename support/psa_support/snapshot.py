"""Trusted operator command: export explicit, non-player pack data. Not callable by the bot."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from .knowledge import document_chunks

# Never ingest world/, logs/, player files, secrets, server.properties, or arbitrary configs.
ROOTS = ('kubejs/server_scripts', 'kubejs/startup_scripts', 'kubejs/data',
         'kubejs/assets/kubejs/lang', 'config/ftbquests/quests', 'patchouli_books')
SUFFIXES = {'.js', '.json', '.snbt', '.md', '.txt'}


def build_snapshot(server: Path, notes: Path | None = None):
    server = server.resolve(strict=True)
    documents, files = [], []
    for prefix in ROOTS:
        root = server/prefix
        if not root.is_dir():
            continue
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(server):
                continue
            if path.suffix not in SUFFIXES or path.stat().st_size > 2_000_000:
                continue
            # Documentation languages relevant to Korean/English retrieval only.
            if any(p in ('zh_cn','zh_tw','ja_jp','ru_ru','de_de','es_es','fr_fr') for p in path.parts):
                continue
            raw = path.read_bytes()
            try:
                text = raw.decode('utf-8')
            except UnicodeDecodeError:
                continue
            relative = str(path.relative_to(server))
            files.append({'path':relative,'sha256':hashlib.sha256(raw).hexdigest()})
            documents.extend(document_chunks(relative,text))
    if notes:
        for path in sorted(notes.glob('*.md')):
            if path.is_symlink() or path.name.startswith('.'):
                continue
            raw = path.read_bytes()
            label = 'operator-notes/'+path.name
            files.append({'path':label,'sha256':hashlib.sha256(raw).hexdigest()})
            documents.extend(document_chunks(label,raw.decode()))
    if not files:
        raise ValueError('No allowlisted pack sources found')
    # Hash jars as deployment identity; never load or execute them.
    mods = []
    for path in sorted((server/'mods').glob('*.jar')):
        if path.is_symlink():
            continue
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream,'sha256').hexdigest()
        mods.append({'name':path.name,'sha256':digest})
    snapshot_id = hashlib.sha256(json.dumps({'files':files,'mods':mods},sort_keys=True).encode()).hexdigest()
    return {'manifest': {'snapshot_id':snapshot_id,'captured_at':datetime.now(timezone.utc).isoformat(),
                         'kind':'static_pack_sources_not_live_world','files':files,'mods':mods},
            'documents':documents}
