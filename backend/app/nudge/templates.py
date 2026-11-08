"""Bilingual message templates (English / Hindi). Every template has both languages with exactly the same placeholders, so
both say the same thing (tests/test_nudge.py checks this). `sms` is the short form used for SMS, WhatsApp and push.

Kernel notices arrive as English sentences without structured fields; their Hindi form carries a Hindi title and summary
and keeps the kernel's detail line verbatim ({detail}). Recorded as a limit in docs/notifications.md.
"""
from __future__ import annotations

import string

T: dict[str, dict[str, dict[str, str]]] = {
    # ---------------------------------------------------------------- maturity reminders (scheduled)
    "reminder_before": {
        "en": {"title": "FDR {fdr_id} matures in {days} days",
               "body": "FDR {fdr_id} ({bank}, {amount}) matures on {maturity}. Renew it or ask for release before that date so the security deposit stays valid.",
               "sms": "AICTE NIDHIVEDA: FDR {fdr_id} matures on {maturity} ({days} days). Renew or request release. {link}"},
        "hi": {"title": "एफडीआर {fdr_id} की परिपक्वता में {days} दिन शेष",
               "body": "एफडीआर {fdr_id} ({bank}, {amount}) {maturity} को परिपक्व होगी। सुरक्षा जमा वैध बनाए रखने के लिए उस तिथि से पहले इसका नवीनीकरण करें या रिलीज़ का अनुरोध करें।",
               "sms": "AICTE निधिवेद: एफडीआर {fdr_id} {maturity} को परिपक्व होगी ({days} दिन)। नवीनीकरण या रिलीज़ अनुरोध करें। {link}"},
    },
    "reminder_missed_renewal": {
        "en": {"title": "Overdue: FDR {fdr_id} matured {days} days ago without renewal",
               "body": "FDR {fdr_id} ({bank}, {amount}) matured on {maturity} and no renewal or replacement has been recorded. The security deposit is not covered until a renewed FDR is submitted.",
               "sms": "AICTE NIDHIVEDA: OVERDUE. FDR {fdr_id} matured on {maturity}, no renewal recorded. Submit the renewed FDR now. {link}"},
        "hi": {"title": "अतिदेय: एफडीआर {fdr_id} {days} दिन पहले बिना नवीनीकरण के परिपक्व हो गई",
               "body": "एफडीआर {fdr_id} ({bank}, {amount}) {maturity} को परिपक्व हो गई और कोई नवीनीकरण या प्रतिस्थापन दर्ज नहीं है। नवीनीकृत एफडीआर जमा होने तक सुरक्षा जमा सुरक्षित नहीं है।",
               "sms": "AICTE निधिवेद: अतिदेय। एफडीआर {fdr_id} {maturity} को परिपक्व हुई, नवीनीकरण दर्ज नहीं। नवीनीकृत एफडीआर अभी जमा करें। {link}"},
    },
    "renewal_gap": {
        "en": {"title": "No bank renewal notice for FDR {fdr_id}",
               "body": "FDR {fdr_id} matured on {maturity}. A renewal was expected but no notice from {bank} has arrived for {days} days.",
               "sms": "AICTE NIDHIVEDA: no bank renewal notice for FDR {fdr_id} (matured {maturity}). {link}"},
        "hi": {"title": "एफडीआर {fdr_id} के लिए बैंक से नवीनीकरण सूचना नहीं",
               "body": "एफडीआर {fdr_id} {maturity} को परिपक्व हुई। नवीनीकरण अपेक्षित था, परंतु {days} दिनों से {bank} की कोई सूचना नहीं आई है।",
               "sms": "AICTE निधिवेद: एफडीआर {fdr_id} (परिपक्व {maturity}) के लिए बैंक नवीनीकरण सूचना नहीं। {link}"},
    },
    # ---------------------------------------------------------------- ladder and escalation
    "rung_up": {
        "en": {"title": "Still waiting: {subject}",
               "body": "This notice was sent on {first_sent} and has not been opened for {days} days, so it has moved up to \"{rung_label}\". {subject}",
               "sms": "AICTE NIDHIVEDA: still waiting on {subject}. Please open it. {link}"},
        "hi": {"title": "अब भी प्रतीक्षा: {subject}",
               "body": "यह सूचना {first_sent} को भेजी गई थी और {days} दिनों से खोली नहीं गई है, इसलिए इसे \"{rung_label}\" स्तर पर बढ़ाया गया है। {subject}",
               "sms": "AICTE निधिवेद: {subject} पर अब भी प्रतीक्षा। कृपया इसे खोलें। {link}"},
    },
    "escalation_copy": {
        "en": {"title": "Escalated to you: {subject}",
               "body": "{from_role} has not acknowledged an overdue item for {days} days. It is now with {to_role}. {subject}",
               "sms": "AICTE NIDHIVEDA: escalated to you, {subject}. {link}"},
        "hi": {"title": "आपको अग्रेषित: {subject}",
               "body": "{from_role} ने {days} दिनों से एक अतिदेय मामले को स्वीकार नहीं किया है। यह अब {to_role} के पास है। {subject}",
               "sms": "AICTE निधिवेद: आपको अग्रेषित, {subject}। {link}"},
    },
    "digest": {
        "en": {"title": "Daily digest: {count} updates",
               "body": "{count} informational updates since the last digest: {summary}",
               "sms": "AICTE NIDHIVEDA: {count} updates in today's digest. {link}"},
        "hi": {"title": "दैनिक सारांश: {count} अपडेट",
               "body": "पिछले सारांश के बाद {count} सूचनात्मक अपडेट: {summary}",
               "sms": "AICTE निधिवेद: आज के सारांश में {count} अपडेट। {link}"},
    },
    # ---------------------------------------------------------------- portal events
    "fdr_submitted": {
        "en": {"title": "New FDR {fdr_id} submitted", "body": "{institution} submitted FDR {fdr_id} ({bank}) for scrutiny.",
               "sms": "AICTE NIDHIVEDA: new FDR {fdr_id} from {institution}. {link}"},
        "hi": {"title": "नई एफडीआर {fdr_id} जमा", "body": "{institution} ने जाँच के लिए एफडीआर {fdr_id} ({bank}) जमा की।",
               "sms": "AICTE निधिवेद: {institution} से नई एफडीआर {fdr_id}। {link}"},
    },
    "fdr_verified": {
        "en": {"title": "FDR {fdr_id} verified", "body": "FDR {fdr_id} is verified: the issuing bank confirmed it and scrutiny is complete.",
               "sms": "AICTE NIDHIVEDA: FDR {fdr_id} verified. {link}"},
        "hi": {"title": "एफडीआर {fdr_id} सत्यापित", "body": "एफडीआर {fdr_id} सत्यापित है: जारीकर्ता बैंक ने इसकी पुष्टि की और जाँच पूरी हुई।",
               "sms": "AICTE निधिवेद: एफडीआर {fdr_id} सत्यापित। {link}"},
    },
    "clarification_required": {
        "en": {"title": "Clarification needed on FDR {fdr_id}", "body": "AICTE needs a clarification on FDR {fdr_id}: {reason}",
               "sms": "AICTE NIDHIVEDA: clarification needed on FDR {fdr_id}. {link}"},
        "hi": {"title": "एफडीआर {fdr_id} पर स्पष्टीकरण आवश्यक", "body": "AICTE को एफडीआर {fdr_id} पर स्पष्टीकरण चाहिए: {reason}",
               "sms": "AICTE निधिवेद: एफडीआर {fdr_id} पर स्पष्टीकरण आवश्यक। {link}"},
    },
    "release_requested": {
        "en": {"title": "Release request {request_id}", "body": "{institution} asked for release of {request_id}.",
               "sms": "AICTE NIDHIVEDA: release request {request_id} from {institution}. {link}"},
        "hi": {"title": "रिलीज़ अनुरोध {request_id}", "body": "{institution} ने {request_id} की रिलीज़ का अनुरोध किया।",
               "sms": "AICTE निधिवेद: {institution} से रिलीज़ अनुरोध {request_id}। {link}"},
    },
    "release_approved": {
        "en": {"title": "Release {request_id} approved", "body": "Release {request_id} was approved ({what}). It is not complete until {until}.",
               "sms": "AICTE NIDHIVEDA: release {request_id} approved. Not complete until {until}. {link}"},
        "hi": {"title": "रिलीज़ {request_id} स्वीकृत", "body": "रिलीज़ {request_id} स्वीकृत हुई ({what})। यह तब तक पूर्ण नहीं है जब तक {until}।",
               "sms": "AICTE निधिवेद: रिलीज़ {request_id} स्वीकृत। पूर्ण नहीं जब तक {until}। {link}"},
    },
    "release_rejected": {
        "en": {"title": "Release {request_id} rejected", "body": "Release {request_id} was rejected: {reason}",
               "sms": "AICTE NIDHIVEDA: release {request_id} rejected. {link}"},
        "hi": {"title": "रिलीज़ {request_id} अस्वीकृत", "body": "रिलीज़ {request_id} अस्वीकृत की गई: {reason}",
               "sms": "AICTE निधिवेद: रिलीज़ {request_id} अस्वीकृत। {link}"},
    },
    "message": {
        "en": {"title": "New message from {sender}", "body": "{sender} wrote: {text}",
               "sms": "AICTE NIDHIVEDA: new message from {sender}. {link}"},
        "hi": {"title": "{sender} से नया संदेश", "body": "{sender} ने लिखा: {text}",
               "sms": "AICTE निधिवेद: {sender} से नया संदेश। {link}"},
    },
    "observation_raised": {
        "en": {"title": "Scrutiny observation on FDR {fdr_id}", "body": "AICTE recorded a {category} observation on FDR {fdr_id}: {text}",
               "sms": "AICTE NIDHIVEDA: scrutiny observation on FDR {fdr_id}. Please reply. {link}"},
        "hi": {"title": "एफडीआर {fdr_id} पर जाँच टिप्पणी", "body": "AICTE ने एफडीआर {fdr_id} पर {category} टिप्पणी दर्ज की: {text}",
               "sms": "AICTE निधिवेद: एफडीआर {fdr_id} पर जाँच टिप्पणी। कृपया उत्तर दें। {link}"},
    },
    "observation_answered": {
        "en": {"title": "Reply on FDR {fdr_id} observation", "body": "{institution} replied to the observation on FDR {fdr_id}: {text}",
               "sms": "AICTE NIDHIVEDA: reply received on FDR {fdr_id}. {link}"},
        "hi": {"title": "एफडीआर {fdr_id} टिप्पणी पर उत्तर", "body": "{institution} ने एफडीआर {fdr_id} की टिप्पणी पर उत्तर दिया: {text}",
               "sms": "AICTE निधिवेद: एफडीआर {fdr_id} पर उत्तर प्राप्त। {link}"},
    },
    "kernel_notice": {
        "en": {"title": "Notice: {kind_label}", "body": "{kind_label} (reference {ref}). {detail}",
               "sms": "AICTE NIDHIVEDA: {kind_label}, reference {ref}. {link}"},
        "hi": {"title": "सूचना: {kind_label}", "body": "{kind_label} (संदर्भ {ref})। विवरण: {detail}",
               "sms": "AICTE निधिवेद: {kind_label}, संदर्भ {ref}। {link}"},
    },
}

# Kernel notice kinds -> (English label, Hindi label, rung)
KERNEL_KINDS: dict[str, tuple[str, str, str]] = {
    "evidence_rejected": ("Bank message rejected", "बैंक संदेश अस्वीकृत", "action"),
    "evidence_invalidated": ("Bank evidence invalidated", "बैंक साक्ष्य अमान्य", "action"),
    "issued_noc_needs_review": ("Issued NOC needs review", "जारी एनओसी की समीक्षा आवश्यक", "action"),
    "refund_needs_review": ("Refund needs review", "रिफ़ंड की समीक्षा आवश्यक", "action"),
    "refund_settled": ("Refund completed", "रिफ़ंड पूर्ण", "info"),
    "payment_returned": ("Payment returned by the bank", "बैंक ने भुगतान लौटाया", "deadline"),
    "refund_returned": ("Your refund was returned", "आपका रिफ़ंड लौटाया गया", "action"),
    "lien_discharged": ("Lien discharged", "ग्रहणाधिकार मुक्त", "info"),
    "payee_name_mismatch": ("Payee name does not match the bank", "प्राप्तकर्ता का नाम बैंक से मेल नहीं खाता", "action"),
    "attribution_dispute": ("Competing claims on a credit", "एक जमा पर प्रतिस्पर्धी दावे", "action"),
    "override_refused": ("Mandatory check override refused", "अनिवार्य जाँच की उपेक्षा अस्वीकृत", "action"),
    "unmatched_instrument": ("Bank confirmation for an unknown FDR", "अज्ञात एफडीआर की बैंक पुष्टि", "action"),
    "lien_anomaly": ("Lien anomaly reported by the bank", "बैंक द्वारा ग्रहणाधिकार विसंगति", "deadline"),
    "renewal_rejected": ("Renewal rejected by the rules", "नियमों द्वारा नवीनीकरण अस्वीकृत", "action"),
    "rule_question": ("Rule question for the legal cell", "विधि प्रकोष्ठ के लिए नियम प्रश्न", "action"),
    "confirmation_overdue": ("Bank credit confirmation overdue", "बैंक जमा पुष्टि अतिदेय", "deadline"),
    "hold_review_due": ("Hold open for 30 days: review due", "रोक 30 दिनों से: समीक्षा आवश्यक", "overdue"),
    "legacy_flagged": ("Legacy record flagged", "पुराना अभिलेख चिह्नित", "info"),
}

EVENT_RUNG = {"fdr_submitted": "info", "fdr_verified": "info", "clarification_required": "action", "release_requested": "action",
              "release_approved": "info", "release_rejected": "action", "message": "info", "observation_raised": "action",
              "observation_answered": "action"}

RUNG_LABEL = {"en": {"info": "Informational", "action": "Action needed", "deadline": "Deadline within 7 days", "overdue": "Overdue"},
              "hi": {"info": "सूचनात्मक", "action": "कार्रवाई आवश्यक", "deadline": "7 दिनों में समय-सीमा", "overdue": "अतिदेय"}}
ROLE_LABEL = {"en": {"institution": "the institution", "aicte": "the AICTE scrutiny officer", "competent_authority": "the competent authority"},
              "hi": {"institution": "संस्थान", "aicte": "AICTE जाँच अधिकारी", "competent_authority": "सक्षम प्राधिकारी"}}
CATEGORY_LABEL = {"en": {"missing_document": "missing document", "mismatch": "mismatch", "query": "query"},
                  "hi": {"missing_document": "अनुपलब्ध दस्तावेज़", "mismatch": "विसंगति", "query": "प्रश्न"}}


def placeholders(s: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(s) if f}


class _Safe(dict):
    def __missing__(self, k: str) -> str:
        return ""


def localise(v, lang: str):
    """A parameter may carry one value per language: {"en": ..., "hi": ...}."""
    if isinstance(v, dict) and v and set(v) <= {"en", "hi"}:
        return v.get(lang, v.get("en"))
    return "" if v is None else v


def render(template: str, lang: str, params: dict, part: str) -> str:
    lang = lang if lang in ("en", "hi") else "en"
    return T[template][lang][part].format_map(_Safe({k: localise(v, lang) for k, v in params.items()})).strip()
