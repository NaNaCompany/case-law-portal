"""Import one reviewed judgment and rebuild; never fetch or bypass source access.
Usage: python scripts/import_reviewed.py /absolute/path/to/reviewed-record.json
The adjacent original HTML must match sourceHtmlFile and sourceHtmlSha256.
"""
from pathlib import Path
import hashlib,json,sys
from build import ROOT,validate_record,records,build,source_digest,image_asset
from privacy_gate import validate_contextual_privacy

def main():
    p=Path(sys.argv[1]).resolve();d=json.loads(p.read_text());validate_record(d)
    source=(p.parent/d['sourcePdfFile' if d.get('sourceType')=='pdf' else 'sourceHtmlFile']).resolve()
    assert source.parent==p.parent,'Original source must be adjacent to record'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_digest(d),'Original HTML hash mismatch'
    image_bytes=[]
    for im in d.get('sourceImages',[]):
        file=(p.parent/im['file']).resolve();assert file.parent==p.parent,'Original image must be adjacent to record'
        b=file.read_bytes();assert hashlib.sha256(b).hexdigest()==im['sha256'],'Original source image hash mismatch'
        image_bytes.append((im,b))
    existing=records();key=lambda x:(x['jurisdiction'],x['court'],x['caseNumber'],x['decisionDate'])
    for old in existing:
        if old['id']==d['id']:
            assert old['fullTextSha256']==d['fullTextSha256'] and key(old)==key(d) and old['sourceUrl']==d['sourceUrl'],'Conflict: review a corrected-source version separately'
            print(json.dumps({'status':'already-imported','id':d['id']}));return
        assert old['sourceUrl']!=d['sourceUrl'] and old['fullTextSha256']!=d['fullTextSha256'] and key(old)!=key(d),'Duplicate judgment'
    validate_contextual_privacy(d)
    created_assets=[]
    for im,b in image_bytes:
        asset=ROOT/image_asset(d,im);assert not asset.exists(),'Unexpected pre-existing image asset'
        asset.parent.mkdir(parents=True,exist_ok=True);asset.write_bytes(b);created_assets.append(asset);im['assetPath']=image_asset(d,im);im.pop('file',None)
    d.pop('sourceHtmlFile',None);d.pop('sourcePdfFile',None)
    dest=ROOT/'data/cases'/f"{d['id']}.json"
    dest.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    try:
        outputs=build()
    except Exception:
        dest.unlink()
        for asset in created_assets:asset.unlink()
        raise
    for name,text in outputs.items():
        file=ROOT/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text)
    print(json.dumps({'status':'imported','id':d['id'],'caseCount':len(existing)+1},ensure_ascii=False))
if __name__=='__main__':main()
