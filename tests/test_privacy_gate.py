import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from privacy_gate import privacy_signals, validate_contextual_privacy
from check_candidate import canonical_source_url
from build import build, records, case_path


class ContextualPrivacy(unittest.TestCase):
    def approved(self):
        return {'fullText':'A commercial legal issue without personal details.',
                'privacyReview':{'contextualReview':{
                    'completeTextRead':True,'privateNamesReviewed':True,
                    'sensitiveFactsReviewed':True,'linkageReviewed':True,
                    'officialMaskingNotAssumed':True,'publicProfessionalNamesDistinguished':True,
                    'decision':'publish-original','unresolvedConcerns':[],
                    'rationale':'All text was read and roles and factual links reviewed; this is a synthetic unit-test fixture only.',
                    'reviewedAt':'2026-11-10T13:00:00+00:00','signalAssessment':{}}}}

    def test_official_masking_does_not_approve_import(self):
        d={'fullText':'Officially public text','privacyReview':{'status':'reviewed-source-anonymization-preserved'}}
        with self.assertRaisesRegex(ValueError,'contextual privacy review'):
            validate_contextual_privacy(d)

    def test_no_signal_is_not_an_approval(self):
        self.assertEqual(privacy_signals('A contract was signed.'),{})
        with self.assertRaises(ValueError):
            validate_contextual_privacy({'fullText':'A contract was signed.'})

    def test_mixed_masking_requires_manual_quarantine(self):
        # Synthetic name token only. Never put an actual exposed source name here.
        d=self.approved();d['fullText']='공소외 1은 가려졌다. 위 가나다와의 내연관계와 그녀의 딸(고교 3년생)을 언급한다.'
        signals=privacy_signals(d['fullText'])
        self.assertIn('possiblePrivateNameInIntimateContext',signals)
        self.assertIn('minorContext',signals)
        review=d['privacyReview']['contextualReview'];review['decision']='hold'
        review['unresolvedConcerns']=['Private-name and intimate/minor context needs quarantine']
        with self.assertRaisesRegex(ValueError,'Privacy hold'):
            validate_contextual_privacy(d)

    def test_specific_signal_assessment_required(self):
        d=self.approved();d['fullText']='The legal citation says Minor, requiring contextual review.'
        with self.assertRaisesRegex(ValueError,'Manual assessment missing'):
            validate_contextual_privacy(d)

    def test_professional_role_is_not_in_law_family_term(self):
        self.assertNotIn('familyLinkage',privacy_signals('회사의 부회장인 소외 2'))

    def test_publication_mode_must_match_review(self):
        d=self.approved();d['privacyEdits']={'verified':True}
        with self.assertRaisesRegex(ValueError,'Privacy hold'):
            validate_contextual_privacy(d)

    def test_source_aliases_cannot_skip_candidate_hold(self):
        self.assertEqual(canonical_source_url('https://law.go.kr/LSW/precInfoP.do?precSeq=123456789'),
                         canonical_source_url('https://www.law.go.kr/precInfoP.do?precSeq=123456789'))

    def test_edited_page_discloses_changes_and_distinct_hashes(self):
        output=build()
        for d in records():
            if d.get('privacyEdits'):
                page=output[case_path(d)+'index.html']
                self.assertIn('privacy-edit-notice',page)
                self.assertIn('추가 비식별 공개본',page)
                self.assertNotIn('class="status-pill">공식 공개 전문',page)
                self.assertIn(d['privacyEdits']['originalFullTextSha256'],page)
                self.assertIn(d['fullTextSha256'],page)
                self.assertNotEqual(d['privacyEdits']['originalFullTextSha256'],d['fullTextSha256'])


if __name__=='__main__':unittest.main()
