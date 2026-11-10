"""Review prompts and a mandatory contextual approval gate for new imports.

Signals are incomplete and can be false positives. No absence of signals, official
publication, or source masking is an anonymity certificate. This module does not
identify people or fetch outside records.
"""
from datetime import datetime
import re


PATTERNS = {
    'intimateRelationship': r'내연|불륜|성관계|성폭력|성추행',
    'minorContext': r'미성년|고교\s*\d\s*년|고등학교|중학생|초등학생|\bMinor\b',
    'possiblePrivateNameInIntimateContext': r'[가-힣]{2,4}[과와]의?\s*(?:내연|불륜|성관계)',
    'familyLinkage': r'조카|배우자|남편|아내|친족|(?<![가-힣])장인|처남|의\s*처[인를가\s]',
    'personalFinancialContext': r'자력|예금잔고|계좌잔액|대출잔액|개인\s*예금|개인\s*재산',
    'contactOrIdentityNumber': r'\b\d{6}-[1-4]\d{6}\b|\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
}


def privacy_signals(text):
    return {name: len(re.findall(pattern, text, re.I)) for name, pattern in PATTERNS.items()
            if re.search(pattern, text, re.I)}


def validate_contextual_privacy(record):
    review = record.get('privacyReview', {}).get('contextualReview', {})
    required = ('completeTextRead', 'privateNamesReviewed', 'sensitiveFactsReviewed',
                'linkageReviewed', 'officialMaskingNotAssumed',
                'publicProfessionalNamesDistinguished')
    if not all(review.get(field) is True for field in required):
        raise ValueError('Complete contextual privacy review is required; official masking is insufficient')
    expected = 'publish-with-labelled-edits' if record.get('privacyEdits') else 'publish-original'
    if review.get('decision') != expected or review.get('unresolvedConcerns') != []:
        raise ValueError('Privacy hold: unresolved concerns cannot be published')
    if not isinstance(review.get('rationale'), str) or len(review['rationale'].strip()) < 30:
        raise ValueError('Record a specific contextual privacy rationale')
    datetime.fromisoformat(review['reviewedAt'])
    addressed = review.get('signalAssessment', {})
    for signal in privacy_signals(record['fullText']):
        if not isinstance(addressed.get(signal), str) or len(addressed[signal].strip()) < 20:
            raise ValueError('Manual assessment missing for privacy signal: ' + signal)
    return record
