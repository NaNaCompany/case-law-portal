import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import records
from import_batch import adjacent, preflight


class BatchPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.record = next(r for r in records() if r['jurisdiction'] == 'KR')
        # This test fixture is local only and always corresponds to an already
        # imported identifier. It cannot add or publish any fictional source.
        self.record['sourceHtmlFile'] = 'source.html'
        raw = b'TEST FIXTURE ONLY: never import or publish this source.'
        self.record['sourceHtmlSha256'] = hashlib.sha256(raw).hexdigest()
        (self.root / 'source.html').write_bytes(raw)
        (self.root / 'record.json').write_text(json.dumps(self.record))
        self.entry = {'id': self.record['id'], 'file': 'record.json'}
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps([self.entry]))

    def tearDown(self):
        self.temp.cleanup()

    def test_existing_record_is_skipped_without_writes(self):
        before = len(records())
        result = preflight(self.manifest)
        self.assertEqual(result[0]['status'], 'already-imported')
        self.assertEqual(len(records()), before)

    def test_reject_corrupt_original(self):
        (self.root / 'source.html').write_text('modified')
        with self.assertRaisesRegex(ValueError, 'Original source digest'):
            preflight(self.manifest)

    def test_reject_duplicate_manifest_entry(self):
        self.manifest.write_text(json.dumps([self.entry, self.entry]))
        with self.assertRaisesRegex(ValueError, 'Repeated manifest'):
            preflight(self.manifest)

    def test_reject_parent_path(self):
        with self.assertRaisesRegex(ValueError, 'one directory'):
            adjacent(self.root, '../outside.json')

    def test_reject_empty_manifest(self):
        self.manifest.write_text('[]')
        with self.assertRaisesRegex(ValueError, '1 to 50'):
            preflight(self.manifest)


if __name__ == '__main__':
    unittest.main()
