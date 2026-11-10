import contextlib
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import BASE, ROOT, case_path, records
from verify_public import JudgmentText, verify


class PublicRelease(unittest.TestCase):
    def local_fetch(self, url):
        if url == 'https://nanalab.kr/sitemap.xml':
            return ('<sitemapindex><sitemap><loc>' + BASE + 'sitemap.xml</loc></sitemap></sitemapindex>').encode()
        self.assertTrue(url.startswith(BASE))
        path = url.removeprefix(BASE)
        if not path or path.endswith('/'):
            path += 'index.html'
        return (ROOT / path).read_bytes()

    def run_verify(self, fetch):
        with contextlib.redirect_stdout(io.StringIO()):
            return verify(fetch)

    def test_local_release_matches(self):
        result = self.run_verify(self.local_fetch)
        self.assertEqual(result['cases'], len(records()))
        self.assertEqual(result['status'], 'passed')

    def test_reject_stale_manifest(self):
        def stale(url):
            raw = self.local_fetch(url)
            if url.endswith('publication.json'):
                data = json.loads(raw)
                data['caseCount'] += 1
                return json.dumps(data).encode()
            return raw
        with self.assertRaisesRegex(ValueError, 'manifest'):
            self.run_verify(stale)

    def test_reject_missing_body(self):
        target = BASE + case_path(records()[0])
        def missing(url):
            raw = self.local_fetch(url)
            return raw.replace(b'class="text', b'class="missing', 1) if url == target else raw
        with self.assertRaisesRegex(ValueError, 'judgment text'):
            self.run_verify(missing)

    def test_reject_stale_asset(self):
        def stale(url):
            raw = self.local_fetch(url)
            return raw + b'changed' if url.endswith('assets/app.js') else raw
        with self.assertRaisesRegex(ValueError, 'asset is stale'):
            self.run_verify(stale)

    def test_text_parser_preserves_entities_and_whitespace(self):
        p = JudgmentText()
        p.feed('<p>Outside</p><div class="text pdf-text">A &amp; B\n  &lt;C&gt;\n</div><div>Ignore</div>')
        self.assertEqual(p.parts, ['A & B\n  <C>\n'])


if __name__ == '__main__':
    unittest.main()
