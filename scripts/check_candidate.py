"""Look up a discovered canonical source URL without making network requests."""
import argparse
import hashlib
import json
from build import ROOT


def lookup(url, publication, ledger):
    for case in publication['cases']:
        if case['sourceUrl'] == url:
            return {'status': 'already-published', 'id': case['id'], 'page': case['url']}
    digest = hashlib.sha256(url.encode()).hexdigest()
    for entry in ledger['entries']:
        if entry['sourceUrlSha256'] == digest:
            return dict(entry)
    return {'status': 'needs-source-review', 'sourceUrlSha256': digest,
            'notice': 'Not previously reviewed. Check source policy, access, privacy and completeness before collection.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', help='Exact canonical URL discovered through a public source')
    args = parser.parse_args()
    publication = json.loads((ROOT / 'publication.json').read_text())
    ledger = json.loads((ROOT / 'data/review-ledger.json').read_text())
    print(json.dumps(lookup(args.url, publication, ledger), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
