"""Deterministic static publisher. Only pre-reviewed records reach public pages."""
from pathlib import Path
from datetime import datetime
import json, hashlib, html, re, sys
from privacy_gate import validate_contextual_privacy
ROOT=Path(__file__).resolve().parents[1]
BASE='https://nanalab.kr/case-law-portal/'
E=lambda value:html.escape(str(value),quote=True)
TODAY='2026-11-10'

def sha(text): return hashlib.sha256(text.encode()).hexdigest()
COUNTRY_NAMES={'KR':'대한민국','IN':'인도'}

def case_path(d):return f"{d['jurisdiction'].lower()}/cases/{d['id']}/"
def source_digest(d):return d['sourcePdfSha256'] if d.get('sourceType')=='pdf' else d['sourceHtmlSha256']
def source_label(d):return 'PDF' if d.get('sourceType')=='pdf' else 'HTML'
def image_asset(d,image):return f"assets/cases/{d['id']}/{image['id']}"+{'image/png':'.png','image/jpeg':'.jpg'}[image['mimeType']]

def validate_record(d):
    required=['id','jurisdiction','court','caseNumber','decisionDate','title','sourceUrl','sourceName','retrievedAt','fullTextSha256','sections','fullText','rights','privacyReview','limitations','review']
    assert all(k in d for k in required),'Missing mandatory metadata'
    assert re.fullmatch(r'[a-z]{2}-[a-z0-9-]+',d['id']),'Unsafe ID'
    assert d['jurisdiction'] in COUNTRY_NAMES,'Jurisdiction requires a reviewed source policy'
    assert d['id'].startswith(d['jurisdiction'].lower()+'-'),'Mismatched country ID'
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}',d['decisionDate']),'Decision date must be YYYY-MM-DD'
    assert d['title'] not in ('판례정보','',None),'Missing case title'
    datetime.fromisoformat(d['decisionDate']);datetime.fromisoformat(d['retrievedAt'])
    assert re.fullmatch('[0-9a-f]{64}',source_digest(d)),'Missing original-source hash'
    assert sha(d['fullText'])==d['fullTextSha256'],'Text integrity mismatch'
    assert all(d['review'].get(k) is True for k in ['verified','metadataVerified','sourceHashVerified','fullTextVerified','rightsBasisReviewed']),'Required source review missing'
    assert len(d['fullText'])>=150 and d['sections'],'No judgment body'
    assert all(isinstance(x.get('text'),str) and x['text'].strip() for x in d['sections'])
    assert d['rights'].get('basis') and d['rights'].get('reuseNoticeUrl'),'Rights evidence missing'
    edits=d.get('privacyEdits')
    if edits:
        assert d['jurisdiction']=='KR','Privacy-edited PDF publication needs separate layout review'
        assert edits.get('verified') is True and edits.get('originalPreservedPrivately') is True,'Privacy edit review missing'
        assert re.fullmatch('[0-9a-f]{64}',edits.get('originalFullTextSha256','')),'Original text provenance missing'
        assert edits['originalFullTextSha256']!=d['fullTextSha256'],'Privacy edits need distinct original and public text hashes'
        assert edits.get('publishedFullTextSha256')==d['fullTextSha256'],'Edited text digest mismatch'
        assert edits.get('summary') and edits.get('categories') and edits.get('limitations'),'Privacy change disclosure missing'
        datetime.fromisoformat(edits['reviewedAt'])
        validate_contextual_privacy(d)
    elif d['privacyReview'].get('contextualReview'):
        validate_contextual_privacy(d)
    if d['jurisdiction']=='KR':
        assert d.get('sourceType','html')=='html','Korean PDF renderer needs separate review'
        assert re.fullmatch(r'https://www\.law\.go\.kr/LSW/precInfoP\.do\?precSeq=\d+',d['sourceUrl']),'Unreviewed source'
        assert d['review'].get('anonymizationPreserved') is True,'Anonymization review missing'
        if edits:
            assert d['review'].get('domCompleteness',{}).get('originalSourceExtractionVerified') is True,'Original extraction review missing'
            assert d['review']['domCompleteness'].get('allTextPreservedIgnoringWhitespace') is False,'Do not label an edited body verbatim'
        else:
            assert d['review'].get('domCompleteness',{}).get('allTextPreservedIgnoringWhitespace') is True,'Incomplete extraction'
        assert not any(d['review']['domCompleteness'].get('nonTextElementCounts',{}).values()),'Non-text structure needs a capable renderer before publication'
        assert '\n\n'.join('【'+x['heading']+'】\n'+x['text'] for x in d['sections'])==d['fullText'],'Section/body integrity mismatch'
        assert d['privacyReview']['status']==('reviewed-additional-privacy-edits' if edits else 'reviewed-source-anonymization-preserved'),'Privacy review missing'
        assert any(re.sub(r'\s','',x['heading'])=='주문' for x in d['sections']),'Missing order'
        assert any(re.sub(r'\s','',x['heading'])=='이유' for x in d['sections']),'Missing reasoning'
        assert not re.search(r'\b\d{6}[- ]?[1-4]\d{6}\b|\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b',d['fullText']),'Possible sensitive identifier'
    else:
        assert d.get('sourceType')=='pdf' and d.get('language')=='en','Unreviewed Indian source format'
        assert re.fullmatch(r'https://api\.sci\.gov\.in/(?:(?:judgment|jonew)/judis/\d+|supremecourt/\d{4}/\d+/[A-Za-z0-9_.-]+)\.pdf',d['sourceUrl']),'Unreviewed source'
        assert d['review'].get('publicationRestrictionChecked') is True and d['rights'].get('publicationRestrictionReview'),'Publication restrictions not reviewed'
        assert d['privacyReview']['status']=='reviewed-public-official-civil-commercial-judgment','Public civil/commercial source review missing'
        if d.get('neutralCitation'):
            assert re.fullmatch(r'\d{4} INSC \d+',d['neutralCitation']),'Unexpected neutral citation format'
            assert re.sub(r'\s','',d['neutralCitation']) in re.sub(r'\s','',d['fullText']),'Neutral citation is absent from original text'
        check=d['review'].get('pdfCompleteness',{})
        assert check.get('pageCount')==check.get('textPages')==len(d['sections']),'Missing PDF pages'
        assert check.get('scanOnlyPages')==0,'Scan-only source needs an OCR review workflow'
        images=d.get('sourceImages',[])
        assert check.get('rasterImages')==len(images),'Not every source raster image is accounted for'
        assert len({image.get('id') for image in images})==len(images),'Duplicate source image ID'
        for image in images:
            assert re.fullmatch(r'[a-z0-9-]+',image.get('id','')),'Unsafe image ID'
            assert image.get('mimeType') in ('image/png','image/jpeg'),'Unreviewed image format'
            assert re.fullmatch(r'[0-9a-f]{64}',image.get('sha256','')),'Image source hash missing'
            assert isinstance(image.get('page'),int) and 1<=image['page']<=check['pageCount'],'Image page missing'
            assert image.get('role')=='official-qr-code','Source image needs substantive review'
            ir=image.get('review',{})
            assert all(ir.get(k) is True for k in ['verified','pixelEqualityVerified','decodedPayloadVerified']) and ir.get('containsCredentialOrNonpublicPersonalData') is False and ir.get('payloadType')=='public-neutral-citation-only','Source image needs pixel and privacy review'
            assert check.get('allRasterImagesAccountedFor') is True and check.get('preservedRasterImages')==len(images) and check.get('omittedRasterImages')==0,'Incomplete image preservation'
            assert image.get('caption'),'Image attribution caption missing'
            if image.get('assetPath'):assert image['assetPath']==image_asset(d,image),'Unexpected image asset path'
        assert all(x.get('rendering')=='preformatted' and x.get('preserveWhitespace') is True for x in d['sections']),'PDF layout preservation missing'
        assert '\f'.join(x['text'] for x in d['sections'])+'\f'==d['fullText'],'Section/body integrity mismatch'
    if d.get('subsequentHistory'):
        history=d['subsequentHistory'];datetime.fromisoformat(history['decisionDate'])
        assert history.get('notice') and history.get('successorCaseNumber') and history.get('sourceUrl','').startswith('https://www.law.go.kr/precInfoP.do?'),'Subsequent-history evidence missing'
    return d

def records():
    ds=[validate_record(json.loads(p.read_text())) for p in sorted((ROOT/'data/cases').glob('*.json'))]
    for d in ds:
        for image in d.get('sourceImages',[]):
            asset=ROOT/image_asset(d,image)
            assert asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest()==image['sha256'],'Missing or modified source image'
    for key in [lambda d:d['id'],lambda d:d['sourceUrl'],lambda d:d['fullTextSha256'],lambda d:(d['jurisdiction'],d['court'],d['caseNumber'],d['decisionDate'])]:
        values=[key(d) for d in ds];assert len(values)==len(set(values)),'Duplicate judgment'
    return sorted(ds,key=lambda d:(d['decisionDate'],d['id']),reverse=True)

TRACK_HEAD='''<script defer src="https://nanalab.kr/src_cdn/banner/astra.js"></script>
<script data-nana-publisher="adsense" async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9767176956440077" crossorigin="anonymous"></script>
<script data-nana-publisher="gtm">(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','GTM-NV2WWQXB');</script>
<script data-nana-publisher="ga4-loader" async src="https://www.googletagmanager.com/gtag/js?id=G-2ZYSF0173P"></script><script data-nana-publisher="ga4-config">window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','G-2ZYSF0173P');</script>'''
TRACK_TAIL='''<script data-nana-publisher="cloudflare-fallback">(function(){function ensureBeacon(){if(document.querySelector('script[src*="static.cloudflareinsights.com/beacon.min.js"]'))return;var b=document.createElement('script');b.defer=true;b.src='https://static.cloudflareinsights.com/beacon.min.js';b.setAttribute('data-cf-beacon',JSON.stringify({token:'9f3423bb0d034d91bbe1a12afeff2429'}));document.head.appendChild(b)}if(document.readyState==='complete')setTimeout(ensureBeacon,0);else window.addEventListener('load',function(){setTimeout(ensureBeacon,0)},{once:true})})();</script>'''

def page(path,title,description,body,active='',structured=None):
    depth=len(Path(path).parts)-1; rel='../'*depth or './'
    cssv=sha((ROOT/'assets/style.css').read_text())[:12];jsv=sha((ROOT/'assets/app.js').read_text())[:12]
    canonical=BASE+('' if path=='index.html' else path.removesuffix('index.html'))
    links=''.join(f'<a href="{rel}{dest}"'+(' aria-current="page"' if active==label else '')+f'>{label}</a>' for dest,label in [('#countries','국가별'),('sources/','출처·수집 기준')])
    ld=json.dumps(structured or {'@context':'https://schema.org','@type':'CollectionPage','name':title,'url':canonical,'inLanguage':'ko'},ensure_ascii=False).replace('<','\\u003c')
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)} | NaNa 판례 자료실</title><meta name="description" content="{E(description)}"><link rel="canonical" href="{canonical}"><meta property="og:title" content="{E(title)} | NaNa 판례 자료실"><meta property="og:description" content="{E(description)}"><meta property="og:type" content="website"><meta property="og:url" content="{canonical}"><meta name="theme-color" content="#142d34"><link rel="stylesheet" href="{rel}assets/style.css?v={cssv}"><script defer src="{rel}assets/app.js?v={jsv}"></script><script type="application/ld+json">{ld}</script>{TRACK_HEAD}</head><body><noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-NV2WWQXB" height="0" width="0" style="display:none;visibility:hidden" title="Google Tag Manager"></iframe></noscript><a class="skip" href="#main">본문 바로가기</a><header class="topbar"><div class="wrap"><a class="brand" href="{rel}"><span class="brand-mark" aria-hidden="true">§</span><span>NaNa 판례 자료실<small>CASE LAW LIBRARY</small></span></a><nav class="nav" aria-label="주요 메뉴">{links}<a class="external" href="https://nanalab.kr/apps/">More Apps ↗</a></nav></div></header><main class="wrap" id="main">{body}</main><footer class="footer"><div class="wrap"><p><strong>NaNa Case Law Library</strong><br>독립 판례 자료실 · 법원 공식 서비스가 아닙니다.<br>수록 범위와 최신성을 보장하지 않으며, 법적 판단 전 공식 원문을 확인하세요.</p><nav aria-label="하단 메뉴"><a href="{rel}sources/">출처·수집 기준</a><a href="{rel}sitemap.xml">사이트맵</a><a href="https://nanalab.kr/world-law-portal/">법령 자료실 ↗</a></nav></div></footer>{TRACK_TAIL}</body></html>'''

def cards(ds,rel):
    if not ds:return '<div class="empty"><h3>판례를 한 건씩 준비하고 있습니다.</h3><p>공식 원문과 이용 조건, 비실명 처리를 확인한 판례부터 개별 페이지로 공개합니다. 아직 수록된 판례는 없습니다.</p></div>'
    return '<ol class="case-list">'+''.join(f'''<li class="case-row" data-case data-search="{E(d['court']+' '+d['caseNumber']+' '+d['title']+' '+d['decisionDate']+' '+d['fullText'])}"><div class="date"><span class="court">{COUNTRY_NAMES[d['jurisdiction']]} · {E(d['court'])}</span><time datetime="{d['decisionDate']}">{d['decisionDate'].replace('-','. ')}</time></div><div><h3><a href="{rel}{case_path(d)}">{E(d['title'])}</a><span class="badge">{'추가 비식별본' if d.get('privacyEdits') else '공식 공개 전문'}</span></h3><p>{E(d['caseNumber'])} · 출처: {E(d['sourceName'])}</p></div><a class="arrow" href="{rel}{case_path(d)}" aria-label="{E(d['caseNumber'])} 판결문 읽기">↗</a></li>''' for d in ds)+'</ol>'

def search():return '''<form class="search-panel" data-search role="search"><label for="case-query">사건번호, 사건명 또는 판결문 문구</label><div class="search-row"><input type="search" id="case-query" name="q" placeholder="예: 2018다276027 · 재판상 자백" autocomplete="off"><button type="submit">검색</button></div><p class="hint">이 페이지에 수록된 판례의 사건명·사건번호·전문에서 검색합니다.</p></form>'''

def sources_body():return '''<p class="breadcrumbs"><a href="../">판례 자료실</a> / 출처·수집 기준</p><div class="page-head"><p class="eyebrow">Provenance &amp; scope</p><h1 class="page-title">어디에서 가져왔고,<br>어떻게 공개하나요?</h1><p class="lead">공개된 판결문과 이용 조건을 함께 확인합니다. 저작권 제외와 무제한 기계 수집 허가는 서로 다른 문제입니다.</p></div><div class="prose"><h2>01. 현재 수록 범위</h2><p>대한민국 국가법령정보센터에서 개별 확인한 공개 판례를 순차 수록합니다. 한국 전체 판례, 모든 공개 판결 또는 모든 최신 판례를 확보했다는 뜻은 아닙니다. 수록 건수는 메인과 국가 목록에 실제 공개 건수만 표시합니다. 각 판례는 하나의 고정된 페이지를 갖습니다.</p><h2>02. 대한민국</h2><p><a href="https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&amp;lsJoLnkSeq=1029423769">저작권법 제7조 제3호</a>는 법원의 판결·결정·명령을 보호받지 못하는 저작물로 정합니다. 민간 출판사의 해설·주석·독창적인 편집물을 이 원칙만으로 복제하지 않습니다.</p><p><a href="https://open.law.go.kr/LSO/usrJoin.do">법제처 법령정보 공동활용 이용 안내</a>의 출처 표시 및 제3자 권리 보호 조건을 따릅니다. 과도한 호출에 대한 제한을 존중하고, 인증이 필요한 API는 등록된 이용 자격이 있을 때만 이용합니다. 테스트용 인증값을 운영 수집에 사용하지 않습니다.</p><p><a href="https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=precInfoGuide">공식 판례 본문 API 안내</a> · <a href="https://openapi.scourt.go.kr/kgso000m04.do">사법정보공유포털 저작권 보호정책</a></p><h2>03. 비실명 처리와 원문 보존</h2><p>공식 공개 여부나 가림표만으로 완전한 비식별을 판단하지 않습니다. 본문의 사적 관계·재산·신원 단서와 결합 가능성을 검토합니다. 추가 비식별한 문서는 별도 표시와 변경 내역을 붙이며, 공식 원문과 동일한 텍스트라고 표시하지 않습니다.</p><p>공식 공개본의 ‘원고’, ‘피고’, ‘소외’ 및 가림표를 그대로 보존하며, 당사자를 추정하거나 다른 자료와 결합해 재식별하지 않습니다. 주문과 이유 등 판결문 전문을 확인하고 출처의 판시사항·판결요지와 구분합니다. 공개된 법률대리인·재판부의 직무상 성명은 원문에 따릅니다.</p><p>판결문에 표·그림·수식·별첨이 있으면 검토 대상에 포함합니다. 재현하지 못한 요소는 누락 위치와 범위를 밝히거나 완전한 전문으로 공개하지 않습니다. 각 페이지의 원문 범위·추출 제한과 공식 출처를 함께 확인하세요.</p><h2 id="international">04. 해외 확대</h2><h3>인도 · 수록 준비</h3><p><a href="https://copyright.gov.in/Copyright_Act_1957/chapter_xi.html">인도 저작권법 제52조 제1항 (q)(iv)</a>는 법원·재판소가 금지하지 않은 판결·명령의 복제와 공표를 허용합니다. Eastern Book Company v. D.B. Modak 판결은 원판결문과 보호될 수 있는 독창적인 편집 기여를 구분합니다. 모든 민간 판례집이 저작권 자유라는 뜻은 아닙니다.</p><p><a href="https://www.wipo.int/wipolex/en/judgments/details/2840">WIPO의 판결 기록</a> · <a href="https://www.sci.gov.in/website-policies/">인도 대법원 웹사이트 정책</a> · <a href="https://scr.sci.gov.in/scrsearch/">공식 eSCR 검색</a></p><p>공식 자료의 접근 조건, 재공표 금지 여부, 개인정보 보호와 수집 경로를 확인한 뒤 공개합니다. CAPTCHA·인증·방화벽을 우회해 수집하지 않습니다. 아직 인도 판례는 수록하지 않았습니다.</p><h3>다른 관할</h3><p>국가별 법률 및 공식 출처의 이용 조건을 확인해 별도로 추가합니다. 한 국가의 재이용 조건을 다른 국가에 적용하지 않습니다.</p><h2>05. 갱신과 정정</h2><p>각 판례에 선고일, 최초 수집일, 최종 검토일, 공식 URL과 본문 해시를 기록합니다. 사건번호·법원·선고일·원문 URL·본문 해시로 중복을 확인합니다. 추가된 페이지는 해당 자료실 사이트맵에 반영되며 NaNa Lab 루트 사이트맵에 연결합니다. 이후 원문이 정정되거나 공개 중단된 경우 재검토 대상이 됩니다.</p><p>누락·오류·비실명 처리에 관한 의견은 <a href="https://nanalab.kr/#contact">NaNa Lab 문의</a>로 정확한 판례 URL과 함께 알려주세요. 법률 자문 서비스가 아니며 법원 인증등본을 대신하지 않습니다.</p><h2>06. 사이트 운영</h2><p>자체 인터페이스와 공식 판결문은 권리 범위를 구분합니다. 사이트에는 NaNa Lab의 공통 방문 분석 및 광고 로더가 포함됩니다. 광고 송출 여부와 분석 수신은 서비스 제공자 설정에 따라 달라질 수 있습니다.</p></div>'''

def build():
    ds=records(); updated=max([d['retrievedAt'][:10] for d in ds]+[TODAY]); n=len(ds);out={}
    krds=[d for d in ds if d['jurisdiction']=='KR']; inds=[d for d in ds if d['jurisdiction']=='IN']; krn=len(krds); inn=len(inds)
    country=f'''<div class="country-grid"><a class="country-card" href="./kr/"><span class="code">KR · REPUBLIC OF KOREA</span><h3>대한민국</h3><p>국가법령정보센터의 공식 공개 판결문</p><div class="count"><strong>{krn:,}건 수록</strong><span>↗</span></div></a><a class="country-card pending" href="./sources/#international"><span class="code">IN · INDIA</span><h3>인도</h3><p>원판결문 권리·접근 조건 검토</p><div class="count"><span>수록 준비</span><span>↗</span></div></a><a class="country-card pending" href="./sources/#international"><span class="code">NEXT · INTERNATIONAL</span><h3>다음 관할</h3><p>국가별 공식 출처와 재이용 조건 확인</p><div class="count"><span>단계별 확대</span><span>↗</span></div></a></div>'''
    if inds:
        country=country.replace('<a class="country-card pending" href="./sources/#international"><span class="code">IN · INDIA</span><h3>인도</h3><p>원판결문 권리·접근 조건 검토</p><div class="count"><span>수록 준비</span><span>↗</span></div></a>',f'<a class="country-card" href="./in/"><span class="code">IN · INDIA</span><h3>인도</h3><p>인도 대법원 공식 공개 원문</p><div class="count"><strong>{inn:,}건 수록</strong><span>↗</span></div></a>')
    home=f'''<section class="hero"><div><p class="eyebrow">Open judgments · Original sources</p><h1>판결의 기록을,<br><em>누구나 읽을 수 있게.</em></h1><p class="lead">대한민국부터 시작하는 공개 판례 자료실.<br>공식 출처와 변경 사항을 확인하며 판결문을 한 건씩 쌓습니다.</p><span class="status-pill">순차 수록 중 · 전체 판례가 아닙니다</span></div><div class="hero-note"><strong>{n:,}</strong><div><span>현재 공개된 판례</span><span>갱신 {updated.replace('-','. ')}</span></div></div></section>{search()}<section id="countries"><div class="section-head"><h2>국가별 자료실</h2><a href="./sources/">수집 기준 보기 ↗</a></div>{country}</section><section><div class="section-head"><h2>최근 선고일순 판례</h2><span>원문 언어 · 개별 페이지</span></div><p class="results-status" data-results>현재 목록 {n}건</p>{cards(ds,'./')}<div class="empty" data-no-results hidden><h3>일치하는 판례가 없습니다.</h3><p>검색어를 줄이거나 사건번호를 확인해 주세요. 미수록 판례는 검색되지 않습니다.</p></div></section><section class="principles" aria-label="공개 원칙"><div><span>01 / ORIGINAL</span><h3>공식 원문을 기준으로</h3><p>판결문과 민간 해설을 구분하고, 모든 문서에 공식 출처를 남깁니다.</p></div><div><span>02 / TRACEABLE</span><h3>판례 한 건, 페이지 하나</h3><p>사건번호·선고일·수집일·본문 해시를 기록해 출처와 변화를 확인합니다.</p></div><div><span>03 / RESPONSIBLE</span><h3>공개 범위를 지킵니다</h3><p>원문의 비실명 처리를 유지하고 국가별 이용 조건을 검토합니다.</p></div></section>'''
    out['index.html']=page('index.html','판례 자료실','공식 출처를 확인한 국내외 판결문을 건별 HTML로 읽는 공개 판례 자료실. 출처·선고일·수집 범위를 함께 확인하세요.',home)
    k=f'''<p class="breadcrumbs"><a href="../">판례 자료실</a> / 대한민국</p><div class="page-head"><p class="eyebrow">KR · Republic of Korea</p><h1 class="page-title">대한민국 판례</h1><p class="lead">공식 출처 기반 판결문 {krn:,}건. 문서별 원문 보존·추가 비식별 내역을 표시합니다.</p><div class="notice">한국 판례 전체를 수록한 목록이 아닙니다. 법원 인증등본이 아니며 공식 공개 전문과 표시된 추가 비식별본을 제공합니다.</div></div>{search()}<div class="section-head"><h2>판례 목록</h2><span>선고일 최신순</span></div><p class="results-status" data-results>현재 목록 {krn}건</p>{cards(krds,'../')}<div class="empty" data-no-results hidden><h3>검색 결과가 없습니다.</h3><p>검색어를 줄이거나 다른 사건번호를 입력해 주세요.</p></div>'''
    out['kr/index.html']=page('kr/index.html','대한민국 판례',f'공식 출처를 확인한 대한민국 판례 {krn}건. 사건번호와 판결문 문구로 검색하고 원문을 읽으세요.',k,'대한민국')
    out['sources/index.html']=page('sources/index.html','출처·수집 기준','판례 자료실의 공식 출처, 저작권과 재이용 조건, 비실명 처리 및 수록 범위를 확인하세요.',sources_body(),'출처·수집 기준')
    if inds:
        india=f'''<p class="breadcrumbs"><a href="../">판례 자료실</a> / 인도</p><div class="page-head"><p class="eyebrow">IN · Republic of India</p><h1 class="page-title">인도 판례</h1><p class="lead">인도 대법원의 공식 공개 원문 {inn:,}건. 원문 영어 그대로 제공합니다.</p><div class="notice">선정된 공개 판결문 자료실이며 인도 판례 전체가 아닙니다. 원판결문과 민간 출판사의 편집물을 구분하고, 재공표 금지 여부와 공식 출처의 이용 조건을 검토합니다.</div></div>{search()}<div class="section-head"><h2>판례 목록</h2><span>선고일 최신순</span></div><p class="results-status" data-results>현재 목록 {inn}건</p>{cards(inds,'../')}<div class="empty" data-no-results hidden><h3>검색 결과가 없습니다.</h3><p>원문의 영어 문구나 사건번호로 검색해 주세요.</p></div>'''
        out['in/index.html']=page('in/index.html','인도 판례',f'인도 대법원의 공식 공개 판결문 {inn}건. 원문 영어·출처·판결일·재이용 조건을 함께 제공합니다.',india)
        out['sources/index.html']=out['sources/index.html'].replace('인도 · 수록 준비','인도 · 공식 원문 수록').replace('아직 인도 판례는 수록하지 않았습니다.',f'인도 대법원 공식 PDF 원문을 {inn}건 수록했습니다.').replace('대한민국 국가법령정보센터에서 개별 확인한 공개 판례를 순차 수록합니다.','대한민국 국가법령정보센터와 인도 대법원 공식 자료에서 개별 확인한 공개 판례를 순차 수록합니다.')
    for i,d in enumerate(ds):
        path=case_path(d)+"index.html";rel='../../../';title=f"{d['title']} · {d['court']} {d['caseNumber']}";sections=''.join(f'<section id="section-{j}"><h2>{E(s["heading"])}'+(' <small class="fineprint">탐색용 표제</small>' if s.get('headingAddedForNavigation') else '')+f'</h2><div class="text'+(' pdf-text' if s.get('rendering')=='preformatted' else '')+f'" lang="{E(d.get("language","ko"))}"'+(' tabindex="0" role="region" aria-label="'+E(s['heading'])+' 원문 고정폭 텍스트"' if s.get('rendering')=='preformatted' else '')+f'>{E(s["text"])}</div>'+''.join(f'<figure class="source-figure"><img src="{rel}{image_asset(d,im)}" alt="{E(im["caption"])}" loading="lazy"><figcaption lang="ko">{E(im["caption"])} · 공식 PDF {im["page"]}쪽에서 추출. 문서 서명을 인증하는 표시가 아닙니다.</figcaption></figure>' for im in d.get('sourceImages',[]) if im['page']==j+1)+'</section>' for j,s in enumerate(d['sections']))
        toc=''.join(f'<li><a href="#section-{j}">{E(s["heading"])}</a></li>' for j,s in enumerate(d['sections']))
        limitations=''.join(f'<li>{E(x)}</li>' for x in d['limitations'])
        history=d.get('subsequentHistory');history_note=(f'<div class="notice history-notice"><strong>후속 판례 안내</strong><p>{E(history["notice"])}</p><a href="{E(history["sourceUrl"])}">{E(history["court"])} {history["decisionDate"]} 선고 {E(history["successorCaseNumber"])} 공식 원문 ↗</a></div>' if history else '')
        citation_meta=f'<div><dt>중립인용</dt><dd>{E(d["neutralCitation"])}</dd></div>' if d.get('neutralCitation') else ''
        edits=d.get('privacyEdits')
        case_badge=('추가 비식별 공개본 · 변경 내역 표시' if edits else '공식 공개 전문 · '+('비실명 표기 유지' if d['jurisdiction']=='KR' else '원문 영어'))
        source_intro=('공식 전문을 바탕으로 일부 정보를 추가 비식별한 자료실 편집본입니다. 아래 변경 안내를 함께 확인하세요.' if edits else ('아래는 공식 페이지의 ‘전문’ 영역입니다. 판시사항·판결요지와 구분해 제공합니다.' if d['jurisdiction']=='KR' else '아래는 공식 PDF의 모든 쪽을 고정폭 텍스트로 재현한 내용입니다. 표와 원문 줄바꿈을 보존하며, 좌우로 이동하여 전체 폭을 확인할 수 있습니다.'))
        privacy_note=(f'<div class="notice privacy-edit-notice"><strong>추가 비식별 안내</strong><p>{E(edits["summary"])}</p><p>{E(edits["limitations"])}</p></div>' if edits else '')
        published_hash_label='공개 편집본 텍스트 SHA-256' if edits else '전문 텍스트 SHA-256'
        original_text_hash=(f'<p class="fineprint">비식별 전 원문 텍스트 SHA-256</p><p class="hash">{edits["originalFullTextSha256"]}</p>' if edits else '')
        description_scope='추가 비식별 공개본' if edits else '공식 공개 전문'
        body=f'''<p class="breadcrumbs"><a href="{rel}">판례 자료실</a> / <a href="../../">{COUNTRY_NAMES[d['jurisdiction']]}</a> / {E(d['caseNumber'])}</p><div class="page-head"><p class="eyebrow">{E(d['court'])} · {d['decisionDate']} 선고</p><h1 class="page-title" lang="{E(d.get('language','ko'))}">{E(d['title'])}</h1><p class="lead">{E(d['court'])} {E(d['caseNumber'])} 판결</p><span class="status-pill">{case_badge}</span></div><div class="notice">출처: {E(d['sourceName'])}. {source_intro} 법원 인증등본은 아니며, 법적 판단 전 <a href="{E(d['sourceUrl'])}" rel="noopener noreferrer" target="_blank">공식 원문 ↗</a>을 확인하세요.</div>{history_note}{privacy_note}<div class="article-grid"><article class="judgment" aria-label="판결문 전문" lang="{E(d.get('language','ko'))}">{sections}<div class="fineprint" lang="ko"><h2>원문 범위와 추출 안내</h2><ul>{limitations}</ul></div></article><aside class="meta" aria-label="판례 정보"><dl><div><dt>법원</dt><dd>{E(d['court'])}</dd></div><div><dt>사건번호</dt><dd>{E(d['caseNumber'])}</dd></div>{citation_meta}<div><dt>선고일</dt><dd>{d['decisionDate']}</dd></div><div><dt>최초 수집일</dt><dd>{d['retrievedAt'][:10]} (UTC)</dd></div><div><dt>최종 검토일</dt><dd>{d['privacyReview']['reviewedAt'][:10]} (UTC)</dd></div><div><dt>공식 출처</dt><dd>{E(d['sourceName'])}</dd></div></dl><a class="button" href="{E(d['sourceUrl'])}" target="_blank" rel="noopener noreferrer">공식 원문 열기 ↗</a><div class="toc"><h2>판결문 목차</h2><ol>{toc}</ol></div><details><summary>출처·권리·본문 해시</summary><p class="fineprint">{E(d['rights']['basis'])}</p><p class="fineprint"><a href="{E(d['rights']['reuseNoticeUrl'])}">공식 재이용 안내</a> · <a href="{rel}sources/">수집 기준</a></p><p class="fineprint">{published_hash_label}</p><p class="hash">{d['fullTextSha256']}</p>{original_text_hash}<p class="fineprint">수집 원본 {source_label(d)} SHA-256</p><p class="hash">{source_digest(d)}</p></details><p><button type="button" class="print-button" data-print>이 판결문 인쇄</button></p></aside></div><nav class="pagination" aria-label="판례 탐색"><a href="../../">← {COUNTRY_NAMES[d['jurisdiction']]} 목록</a>'''+(f'<a href="{rel}{case_path(ds[i+1])}">다음 판례 →</a>' if i+1<len(ds) else '')+'</nav>'
        structured={'@context':'https://schema.org','@type':'DigitalDocument','name':title,'url':BASE+path.removesuffix('index.html'),'inLanguage':d.get('language','ko'),'datePublished':d['retrievedAt'][:10],'dateModified':d['privacyReview']['reviewedAt'][:10],'isBasedOn':d['sourceUrl'],'citation':d['sourceUrl'],'identifier':d['caseNumber'],'about':{'@type':'Thing','name':d['court']+' '+d['decisionDate']+' 선고 '+d['caseNumber']}}
        out[path]=page(path,title,f"{d['court']} {d['decisionDate']} 선고 {d['caseNumber']} {d['title']} 판결. {description_scope}과 출처·권리·비실명 처리 안내.",body,'대한민국',structured)
    urls=[BASE+p.removesuffix('index.html') for p in out]
    assert len(urls)<45000,'Partition static lists and leaf sitemaps before exceeding 45,000 pages'
    out['sitemap.xml']='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join(f'  <url><loc>{E(u)}</loc><lastmod>{updated}</lastmod></url>\n' for u in urls)+'</urlset>\n'
    out['publication.json']=json.dumps({'schemaVersion':1,'updated':updated,'caseCount':n,'privacyEditedCaseCount':sum(bool(d.get('privacyEdits')) for d in ds),'jurisdictions':{k:sum(d['jurisdiction']==k for d in ds) for k in COUNTRY_NAMES if any(d['jurisdiction']==k for d in ds)},'scope':'Selected reviewed judgments; not exhaustive','oneCasePerPage':True,'cases':[{'id':d['id'],'url':BASE+case_path(d),'sourceUrl':d['sourceUrl'],'fullTextSha256':d['fullTextSha256'],**({'publicationMode':'privacy-edited','originalFullTextSha256':d['privacyEdits']['originalFullTextSha256']} if d.get('privacyEdits') else {})} for d in ds]},ensure_ascii=False,indent=2)+'\n'
    return out

if __name__=='__main__':
    out=build();check='--check' in sys.argv
    for path,text in out.items():
        p=ROOT/path
        if check:assert p.is_file() and p.read_text()==text,'Stale generated file: '+path
        else:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    print(json.dumps({'status':'checked' if check else 'built','caseCount':len(records()),'outputs':len(out)},ensure_ascii=False))
