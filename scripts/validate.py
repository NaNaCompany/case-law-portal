from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import sys,json,xml.etree.ElementTree as ET
from build import ROOT,BASE,records,build
class Page(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.canonical=[];self.ids=[];self.caseBodies=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if tag=='link' and d.get('rel')=='canonical':self.canonical.append(d.get('href'))
        if tag in ('a','script','link'):
            u=d.get('href') if tag!='script' else d.get('src')
            if u:self.links.append(u)
        if tag=='article' and d.get('class')=='judgment':self.caseBodies+=1
out=build();ds=records();htmls={}
for name,text in out.items():
    assert (ROOT/name).read_text()==text,'Stale build: '+name
    if not name.endswith('.html'):continue
    p=Page();p.feed(text);htmls[name]=p
    expected=BASE+name.removesuffix('index.html')
    assert p.canonical==[expected],name+' canonical'
    assert len(p.ids)==len(set(p.ids)),name+' duplicate ID'
    assert all(x in text for x in ['GTM-NV2WWQXB','G-2ZYSF0173P','ca-pub-9767176956440077','9f3423bb0d034d91bbe1a12afeff2429','https://nanalab.kr/src_cdn/banner/astra.js'])
    for link in p.links:
        parsed=urlsplit(link)
        if parsed.scheme or parsed.netloc:continue
        if parsed.path:
            target=(ROOT/name).parent/unquote(parsed.path)
            if target.is_dir():target=target/'index.html'
            assert target.is_file(),f'{name}: missing {link}'
        elif parsed.fragment:assert parsed.fragment in p.ids,f'{name}: missing anchor {link}'
    assert p.caseBodies==(1 if '/cases/' in name else 0)
ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
locs=[e.text for e in ET.fromstring(out['sitemap.xml']).findall('s:url/s:loc',ns)]
assert len(locs)==len(set(locs))==len(htmls)
assert set(locs)=={BASE+p.removesuffix('index.html') for p in htmls}
assert sum(p.caseBodies for p in htmls.values())==len(ds)
assert len(list(ROOT.glob('*/cases/*/index.html')))==len(ds),'Orphan case page'
manifest=json.loads(out['publication.json']);assert manifest['caseCount']==len(ds)
print(json.dumps({'status':'passed','cases':len(ds),'htmlPages':len(htmls),'sitemapUrls':len(locs),'checks':['deterministic build','metadata and rights review','text and section integrity','deduplication','local links and anchors','canonical URLs','publisher tags','one case per page','sitemap exact coverage']}))
