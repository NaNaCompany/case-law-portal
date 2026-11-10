import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import ROOT
from check_candidate import lookup,assert_unheld_source,canonical_source_url


class CandidateLedger(unittest.TestCase):
    def test_published_source(self):
        publication = json.loads((ROOT / 'publication.json').read_text())
        case = publication['cases'][0]
        result = lookup(case['sourceUrl'], publication, {'entries': []})
        self.assertEqual(result['status'], 'already-published')
        self.assertEqual(result['id'], case['id'])

    def test_held_source_is_not_retried(self):
        url = 'https://example.test/source'
        entry = {'sourceUrlSha256': hashlib.sha256(url.encode()).hexdigest(),
                 'status': 'held-for-review', 'automaticRetry': False}
        self.assertEqual(lookup(url, {'cases': []}, {'entries': [entry]}), entry)

    def test_unknown_source_requires_review(self):
        result = lookup('https://example.test/new', {'cases': []}, {'entries': []})
        self.assertEqual(result['status'], 'needs-source-review')

    def test_import_must_resolve_existing_quarantine(self):
        canonical='https://www.law.go.kr/LSW/precInfoP.do?precSeq=123456789'
        ledger={'entries':[{'sourceUrlSha256':hashlib.sha256(canonical.encode()).hexdigest(),
                            'status':'held-for-review','automaticRetry':False}]}
        with self.assertRaisesRegex(ValueError,'quarantined'):
            assert_unheld_source('https://law.go.kr/precInfoP.do?precSeq=123456789',ledger)

    def test_ledger_has_no_unpublished_urls_or_personal_content(self):
        data = json.loads((ROOT / 'data/review-ledger.json').read_text())
        hashes = set()
        for entry in data['entries']:
            self.assertEqual(set(entry), {'sourceUrlSha256', 'status', 'reasonCategory',
                                         'reviewedAt', 'automaticRetry'})
            self.assertRegex(entry['sourceUrlSha256'], r'^[0-9a-f]{64}$')
            self.assertFalse(entry['automaticRetry'])
            self.assertIn(entry['status'], ('held-for-review', 'temporarily-unavailable'))
            self.assertIn(entry['reasonCategory'], ('incomplete-source', 'source-quality-review',
                                                   'essential-visual-missing', 'privacy-review', 'http-503'))
            self.assertNotIn(entry['sourceUrlSha256'], hashes)
            hashes.add(entry['sourceUrlSha256'])


if __name__ == '__main__':
    unittest.main()
