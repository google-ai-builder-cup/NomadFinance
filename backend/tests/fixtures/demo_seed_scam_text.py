# ruff: noqa: E501  (a table of sentences: a line is a sentence)
"""The words of the demo workers' stored scam checks, in Hindi and Tagalog (NF-HR-003).

The explainer of a stored check is in the worker's language (`users.preferred_language`): Hindi
for Priya and Rajesh, Tagalog for Miguel. The messages are rows of the reviewed golden sets
(`data-scripts/evals/scam_golden_*.jsonl`), so the labels (type, tactics, risk) are not new
judgements; what is written here is the explanation a worker reads. Written by the team, not by a
native speaker (docs/deferred-items.md, the NF-HR-003 entry).
"""

from __future__ import annotations

from dataclasses import dataclass

LANGS = ("hi", "tl")

TACTIC_WHY: dict[str, dict[str, str]] = {
    "urgency": {
        "hi": "यह आपको जल्दबाज़ी में डालता है ताकि आप सोचने से पहले कदम उठा लें।",
        "tl": "Pinagmamadali ka nito para kumilos ka bago mag-isip.",
    },
    "scarcity": {
        "hi": "यह कहता है कि बस कुछ जगहें बची हैं, ताकि आपको लगे कि अभी हाँ कहनी है।",
        "tl": "Sinasabi nitong kakaunti na lang ang natitira, para pakiramdam mo kailangan mo nang um-oo ngayon.",
    },
    "fear": {
        "hi": "यह खाता बंद होने या जुर्माने का डर दिखाता है ताकि आप जल्दी करें।",
        "tl": "Tinatakot ka nito na masasara ang account o may multa para magmadali ka.",
    },
    "authority": {
        "hi": "यह बैंक या किसी अधिकारी का रूप धरता है ताकि आप भरोसा कर लें।",
        "tl": "Nagpapanggap itong bangko o opisyal para pagkatiwalaan mo.",
    },
}

# What the sender wants, and three safe steps, for each kind of scam the demo uses.
SCAM_TYPE: dict[str, dict[str, tuple[str, list[str]]]] = {
    "illegal_recruitment_fee": {
        "hi": (
            "आपका पैसा, किसी असली अनुबंध से पहले।",
            [
                "अभी कोई पैसा न दें।",
                "एजेंसी से उसका लाइसेंस नंबर माँगें और सरकारी दफ़्तर से खुद जाँचें।",
                "यह संदेश किसी मज़दूर सहायता संगठन या श्रम कार्यालय को दिखाएँ।",
            ],
        ),
        "tl": (
            "Ang pera mo, bago pa may totoong kontrata.",
            [
                "Huwag munang magbayad ng kahit ano.",
                "Hingin sa ahensya ang lisensya nito at ikaw mismo ang mag-verify sa tanggapan ng gobyerno.",
                "Ipakita ang mensahe sa samahang tumutulong sa manggagawa o sa labor office.",
            ],
        ),
    },
    "fake_job_offer": {
        "hi": (
            "आपके पासपोर्ट की कॉपी और बैंक की जानकारी, या कोई फीस।",
            [
                "अपने दस्तावेज़ या बैंक की जानकारी न भेजें।",
                "नियोक्ता या एजेंसी को खुद ढूँढें और उसकी आधिकारिक वेबसाइट के नंबर पर फ़ोन करें।",
                "जवाब देने से पहले किसी दोस्त या सहायता संगठन को बताएँ।",
            ],
        ),
        "tl": (
            "Kopya ng passport at detalye ng bank mo, o bayad.",
            [
                "Huwag magpadala ng dokumento o detalye ng bank.",
                "Hanapin mo mismo ang employer o ahensya at tawagan ang numero sa opisyal nitong website.",
                "Sabihin sa kaibigan o sa samahan bago sumagot.",
            ],
        ),
    },
    "remittance_otp_phishing": {
        "hi": (
            "आपके फ़ोन पर आया कोड, ताकि वह आपका पैसा निकाल सके।",
            [
                "कोड किसी को न बताएँ, भले ही वे खुद को बैंक कहें।",
                "लिंक न खोलें। अपना बैंक या ट्रांसफ़र ऐप खुद खोलें।",
                "अपने कार्ड पर छपे नंबर पर बैंक को फ़ोन करें।",
            ],
        ),
        "tl": (
            "Ang code sa phone mo, para makuha nila ang pera mo.",
            [
                "Huwag ibigay ang code kaninuman, kahit sabihing sila ang bangko.",
                "Huwag buksan ang link. Ikaw mismo ang magbukas ng bank o transfer app mo.",
                "Tawagan ang bangko mo sa numerong nakalimbag sa card mo.",
            ],
        ),
    },
    "loan_app_trap": {
        "hi": (
            "आपसे ऐसा ऐप इंस्टॉल करवाना जो आपका डेटा ले ले और ज़्यादा पैसे वसूले।",
            [
                "ऐप इंस्टॉल न करें।",
                "लोन के लिए अपनी फ़ोटो या कॉन्टैक्ट्स का एक्सेस कभी न दें।",
                "कोई फ़ैसला करने से पहले मज़दूर सहायता संगठन से बात करें।",
            ],
        ),
        "tl": (
            "Na mag-install ka ng app na kukuha ng data mo at maniningil ng mas malaki.",
            [
                "Huwag i-install ang app.",
                "Huwag magbigay ng access sa mga litrato o contact mo kapalit ng utang.",
                "Makipag-usap sa samahang tumutulong sa manggagawa bago magdesisyon.",
            ],
        ),
    },
}

# For a message that is not a scam: what is fine about it, and one habit to keep.
BENIGN: dict[str, dict[str, tuple[str, str]]] = {
    "agency_no_fee": {
        "hi": (
            "इस संदेश में लिखा है कि आपको कोई फीस नहीं देनी है, जो नियम के अनुसार है।",
            "अगर कोई नौकरी के लिए पैसे माँगे तो न दें और किसी सहायता संगठन को बताएँ।",
        ),
        "tl": (
            "Sinasabi ng mensaheng ito na wala kang babayarang placement fee, na ayon sa patakaran.",
            "Kung may humingi ng pera para sa trabaho, huwag magbayad at sabihin sa isang samahang tumutulong.",
        ),
    },
    "work_permit_reminder": {
        "hi": (
            "यह एक सामान्य याद-दिलाने वाला संदेश है। यह न पैसा माँगता है, न लिंक।",
            "नवीनीकरण के लिए आधिकारिक वेबसाइट खुद खोलें, संदेश के लिंक से नहीं।",
        ),
        "tl": (
            "Karaniwang paalala ito. Hindi ito humihingi ng pera o link.",
            "Mag-renew sa opisyal na website na ikaw mismo ang nagbukas, hindi sa link sa mensahe.",
        ),
    },
    "bank_deposit_reminder": {
        "hi": (
            "यह बैंक की सामान्य सूचना है। इसमें आपसे कुछ नहीं माँगा गया है।",
            "लिंक की जगह अपना बैंक ऐप खुद खोलकर देखें।",
        ),
        "tl": (
            "Karaniwang abiso ito ng bangko. Wala itong hinihingi sa iyo.",
            "Buksan mo mismo ang bank app mo sa halip na sumunod sa kahit anong link.",
        ),
    },
    "loan_instalment_reminder": {
        "hi": (
            "यह किस्त की सामान्य याद-दिलाई है, बिना लिंक और बिना धमकी के।",
            "भुगतान में दिक्कत हो तो उसी नंबर पर फ़ोन करें जो आपके पास पहले से है।",
        ),
        "tl": (
            "Karaniwang paalala ito ng hulog, walang link at walang banta.",
            "Kung nahihirapan kang magbayad, tawagan ang numerong hawak mo na.",
        ),
    },
    "interview_notice": {
        "hi": (
            "यह इंटरव्यू की सामान्य सूचना है। इसमें कोई पैसा नहीं माँगा गया है।",
            "जाने से पहले एजेंसी का लाइसेंस खुद जाँच लें।",
        ),
        "tl": (
            "Karaniwang abiso ito ng interview. Walang hinihinging bayad.",
            "Suriin mo mismo ang lisensya ng ahensya bago pumunta.",
        ),
    },
    "otp_notice": {
        "hi": (
            "यह वन-टाइम पासवर्ड का सामान्य संदेश है। यह आपसे कुछ नहीं माँगता।",
            "कोड किसी को न बताएँ, भले ही वह खुद को बैंक कहे।",
        ),
        "tl": (
            "Karaniwang mensahe ito ng one-time password. Wala itong hinihingi sa iyo.",
            "Huwag ibigay ang code kaninuman, kahit sabihing sila ang bangko.",
        ),
    },
}


@dataclass(frozen=True)
class Pick:
    """One stored check: a golden row, how to explain it, the phrases that give it away."""

    row_id: str
    phrases: tuple[str, ...]
    benign_note: str | None = None
    days_ago: int = 1
    hour_utc: int = 9


# Each worker's five checks, newest first. `phrases` are substrings of the masked message.
PICKS: dict[str, list[Pick]] = {
    "priya_sg_domestic": [
        Pick("gold-hi-002", ("एजेंसी फीस 1,50,000 रुपये कल तक",), days_ago=2, hour_utc=7),
        Pick("gold-en-013", (), benign_note="work_permit_reminder", days_ago=6, hour_utc=11),
        Pick(
            "gold-bn-001",
            ("মাত্র ৩টি পদ বাকি", "আজই আপনার পাসপোর্টের ছবি"),
            days_ago=11,
            hour_utc=14,
        ),
        Pick(
            "gold-hi-005",
            ("तुरंत लोन, कोई कागज़ नहीं", "7 दिन में चुकाना होगा"),
            days_ago=19,
            hour_utc=6,
        ),
        Pick("gold-hi-006", (), benign_note="agency_no_fee", days_ago=27, hour_utc=10),
    ],
    "rajesh_kr_manufacturing": [
        Pick("gold-ne-002", ("म्यानपावर शुल्क रु. 1,80,000 भोलिसम्म",), days_ago=3, hour_utc=5),
        Pick(
            "gold-hi-014",
            ("aapka bank account aaj band ho jayega", "OTP is number par bata dein"),
            days_ago=8,
            hour_utc=12,
        ),
        Pick("gold-en-016", (), benign_note="loan_instalment_reminder", days_ago=13, hour_utc=8),
        Pick(
            "gold-hi-011",
            ("Interview ki zarurat nahi", "Abhi WhatsApp karo"),
            days_ago=21,
            hour_utc=15,
        ),
        Pick("gold-hi-016", (), benign_note="bank_deposit_reminder", days_ago=33, hour_utc=9),
    ],
    "miguel_jp_care": [
        Pick(
            "gold-tl-004",
            ("Naka-hold ang padala mong 60,000 JPY", "ilagay ang OTP na matatanggap mo"),
            days_ago=1,
            hour_utc=4,
        ),
        Pick("gold-tl-006", (), benign_note="interview_notice", days_ago=7, hour_utc=10),
        Pick(
            "gold-en-012",
            ("send a placement fee of 90,000 PHP", "before Friday"),
            days_ago=12,
            hour_utc=13,
        ),
        Pick("gold-id-002", (), benign_note="otp_notice", days_ago=22, hour_utc=7),
        Pick(
            "gold-tl-005",
            ("walang requirements, walang credit check", "Bayaran sa loob ng 7 araw"),
            days_ago=30,
            hour_utc=16,
        ),
    ],
}
