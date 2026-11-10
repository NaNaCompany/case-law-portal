import sys,unittest,copy,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build import validate_record,records,build
class Integrity(unittest.TestCase):
 def test_deterministic_build(self): self.assertEqual(build(),build())
 def test_all_records(self):
  for d in records():self.assertEqual(validate_record(d),d)
 def test_reject_tampering(self):
  for d in records():
   bad=copy.deepcopy(d);bad['sections'][0]['text']+='Changed'
   with self.assertRaises(AssertionError):validate_record(bad)
 def test_reject_unreviewed(self):
  for d in records():
   bad=copy.deepcopy(d);bad['review']['verified']=False
   with self.assertRaises(AssertionError):validate_record(bad)
 def test_reject_unsafe_id(self):
  for d in records():
   bad=copy.deepcopy(d);bad['id']='../../overwrite'
   with self.assertRaises(AssertionError):validate_record(bad)
 def test_reject_nontext_omission(self):
  for d in records():
   bad=copy.deepcopy(d)
   if d.get('sourceType')=='pdf':bad['review']['pdfCompleteness']['rasterImages']+=1
   else:bad['review']['domCompleteness']['nonTextElementCounts']['table']=1
   with self.assertRaises(AssertionError):validate_record(bad)
if __name__=='__main__':unittest.main()
