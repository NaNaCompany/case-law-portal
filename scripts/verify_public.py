"""Verify the deployed site against this checkout; read-only and no source crawling.

Run after GitHub Pages has built the intended commit. A stale deployment fails
rather than being reported as published. Optional reports stay in artifacts/.
"""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import argparse
import hashlib
import html
import json
import time
import xml.etree.ElementTree as ET

from build import BASE, ROOT, case_path, records, source_digest


class JudgmentText(HTMLParser):
    """Read escaped judgment text, not ads, navigation or editorial notices."""
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        if tag != 'div':
            return
        if self.depth:
            self.depth += 1
        elif 'text' in dict(attrs).get('class', '').split():
            self.depth = 1
            self.buffer = []

    def handle_endtag(self, tag):
        if tag == 'div' and self.depth:
            self.depth -= 1
            if not self.depth:
                self.parts.append(''.join(self.buffer))

    def handle_data(self, value):
        if self.depth:
            self.buffer.append(value)


def locations(raw):
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    return [e.text for e in ET.fromstring(raw).findall('s:url/s:loc', ns)]


def fetch(url):
    # Only the user's own public deployment is fetched by this verifier.
    if not url.startswith('https://nanalab.kr/'):
        raise ValueError('Verification is restricted to the published NaNa site')
    url += ('&' if '?' in url else '?') + 'verify=' + str(time.time_ns())
    req = Request(url, headers={'User-Agent': 'NaNa-Case-Law-Release-Check/1.0'})
    with urlopen(req, timeout=35) as response:
        if response.status != 200:
            raise ValueError(f'Unexpected status: {response.status}')
        data = response.read()
    time.sleep(0.2)
    return data


def verify(get=fetch, workers=1):
    expected = json.loads((ROOT / 'publication.json').read_text())
    if json.loads(get(BASE + 'publication.json')) != expected:
        raise ValueError('Published manifest does not match this checkout')
    for asset in ['assets/style.css', 'assets/app.js']:
        if get(BASE + asset) != (ROOT / asset).read_bytes():
            raise ValueError('Published asset is stale: ' + asset)
    ds = records()
    def check_record(record):
        image_count = 0
        raw = get(BASE + case_path(record)).decode('utf-8')
        parsed = JudgmentText()
        parsed.feed(raw)
        if parsed.parts != [section['text'] for section in record['sections']]:
            raise ValueError('Published judgment text differs: ' + record['id'])
        for digest in [record['fullTextSha256'], source_digest(record)]:
            if digest not in raw:
                raise ValueError('Missing published provenance: ' + record['id'])
        if record.get('subsequentHistory'):
            if html.escape(record['subsequentHistory']['notice'], quote=True) not in raw:
                raise ValueError('Missing subsequent-history notice: ' + record['id'])
        if record.get('neutralCitation'):
            if '<dt>중립인용</dt><dd>' + record['neutralCitation'] + '</dd>' not in raw:
                raise ValueError('Missing neutral-citation metadata: ' + record['id'])
        for image in record.get('sourceImages', []):
            if image['assetPath'] not in raw:
                raise ValueError('Missing source image: ' + record['id'])
            if hashlib.sha256(get(BASE + image['assetPath'])).hexdigest() != image['sha256']:
                raise ValueError('Modified published source image: ' + record['id'])
            image_count += 1
        return record['id'], image_count
    # Default to sequential reads. Optional bounded concurrency never targets courts.
    image_count = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for identifier, images in pool.map(check_record, ds):
            image_count += images
            print(identifier, 'verified', flush=True)
    for jurisdiction, count in expected['jurisdictions'].items():
        raw = get(BASE + jurisdiction.lower() + '/').decode('utf-8')
        if raw.count('data-case ') != count:
            raise ValueError('Published country count differs: ' + jurisdiction)
    local_urls = locations((ROOT / 'sitemap.xml').read_bytes())
    public_urls = locations(get(BASE + 'sitemap.xml'))
    if len(public_urls) != len(set(public_urls)) or set(public_urls) != set(local_urls):
        raise ValueError('Published sitemap differs from the reviewed release')
    if (BASE + 'sitemap.xml').encode() not in get('https://nanalab.kr/sitemap.xml'):
        raise ValueError('Portal sitemap is missing from the root sitemap')
    return {
        'status': 'passed',
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'cases': len(ds),
        'jurisdictions': expected['jurisdictions'],
        'sourceImages': image_count,
        'sitemapUrls': len(public_urls),
        'rootLinked': True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='Optional local JSON report path')
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=1,
                        help='Concurrent checks of our own deployment (default: 1)')
    args = parser.parse_args()
    result = verify(workers=args.workers)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
