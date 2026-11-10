"""Preflight a bounded reviewed manifest. No network access or publication.

Defaults to dry-run. --apply imports each reviewed record only after the entire
manifest, source hashes and duplicate/conflict checks have passed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

from build import ROOT, records, source_digest, validate_record


def adjacent(base, filename):
    path = (base / filename).resolve()
    if path.parent != base:
        raise ValueError('Manifest and source files must stay in one directory')
    return path


def case_key(record):
    return tuple(record[k] for k in ('jurisdiction', 'court', 'caseNumber', 'decisionDate'))


def preflight(manifest):
    manifest = Path(manifest).resolve()
    entries = json.loads(manifest.read_text())
    if not isinstance(entries, list) or not 1 <= len(entries) <= 50:
        raise ValueError('Use a reviewed manifest containing 1 to 50 records')
    existing = records()
    by_id = {r['id']: r for r in existing}
    identifiers = set()
    result = []
    for entry in entries:
        identifier = entry['id']
        if identifier in identifiers:
            raise ValueError('Repeated manifest identifier: ' + identifier)
        identifiers.add(identifier)
        filename = entry.get('file') or identifier.removeprefix('kr-law-') + '.json'
        path = adjacent(manifest.parent, filename)
        record = validate_record(json.loads(path.read_text()))
        if record['id'] != identifier:
            raise ValueError('Manifest identifier differs from reviewed record')
        for field in ('fullTextSha256', 'sourceHtmlSha256', 'sourcePdfSha256'):
            if field in entry and entry[field] != record.get(field):
                raise ValueError('Manifest digest differs from reviewed record: ' + identifier)
        source_field = 'sourcePdfFile' if record.get('sourceType') == 'pdf' else 'sourceHtmlFile'
        source = adjacent(manifest.parent, record[source_field])
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_digest(record):
            raise ValueError('Original source digest differs: ' + identifier)
        for image in record.get('sourceImages', []):
            source_image = adjacent(manifest.parent, image['file'])
            if hashlib.sha256(source_image.read_bytes()).hexdigest() != image['sha256']:
                raise ValueError('Original image digest differs: ' + identifier)
        old = by_id.get(identifier)
        if old:
            if (old['fullTextSha256'], case_key(old), old['sourceUrl']) != (
                    record['fullTextSha256'], case_key(record), record['sourceUrl']):
                raise ValueError('Conflicting correction needs separate review: ' + identifier)
            status = 'already-imported'
        else:
            if any(record['sourceUrl'] == other['sourceUrl'] or
                   record['fullTextSha256'] == other['fullTextSha256'] or
                   case_key(record) == case_key(other) for other in existing):
                raise ValueError('Duplicate judgment: ' + identifier)
            status = 'ready'
            existing.append(record)
            by_id[identifier] = record
        result.append({'id': identifier, 'status': status, 'file': str(path)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    result = preflight(args.manifest)
    print(json.dumps({'mode': 'apply' if args.apply else 'dry-run', 'records': result},
                     ensure_ascii=False, indent=2), flush=True)
    if args.apply:
        for item in result:
            if item['status'] == 'ready':
                subprocess.run([sys.executable, str(ROOT / 'scripts/import_reviewed.py'),
                                item['file']], check=True)
        print('Local import finished. Validate, review, commit and deploy separately.')


if __name__ == '__main__':
    main()
