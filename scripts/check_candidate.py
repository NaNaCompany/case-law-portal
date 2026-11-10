"""Look up a discovered canonical source URL without making network requests."""
import argparse
import hashlib
import json
from urllib.parse import urlsplit, parse_qs
from build import ROOT


def canonical_source_url(url):
    parsed=urlsplit(url)
    ids=parse_qs(parsed.query).get('precSeq', [])
    if parsed.hostname in ('law.go.kr','www.law.go.kr') and parsed.path in ('/LSW/precInfoP.do','/precInfoP.do') and len(ids)==1 and ids[0].isdigit():
        return 'https://www.law.go.kr/LSW/precInfoP.do?precSeq='+ids[0]
    return url


def assert_unheld_source(url, ledger):
    digest=hashlib.sha256(canonical_source_url(url).encode()).hexdigest()
    if any(entry['sourceUrlSha256']==digest for entry in ledger['entries']):
        raise ValueError('Source is quarantined; a separate documented review must resolve the ledger hold before import')


def lookup(url, publication, ledger):
    url=canonical_source_url(url)
    for case in publication['cases']:
        if canonical_source_url(case['sourceUrl']) == url:
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
