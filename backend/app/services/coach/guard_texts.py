"""The fixed words of the Coach guard, in the six languages (NF-FC-013).

Written once, here, not by a model: a safety message and the "not professional financial advice"
note must not change from one run to the next, and a model that improvises a referral could invent
a phone number. The referral names no organisation and holds no number on purpose (the repository
has no sourced contact data, and a wrong number is worse than none); a test holds it to that.

Short sentences of everyday words, for a worker who reads the language as a second one. Written by
the team, not read by native speakers yet.
"""

from __future__ import annotations

from app.schemas.contract import ReportLanguage
from app.services.coach.guard_types import GuardDecision


def _say(*sentences: str) -> str:
    return " ".join(sentences)


# Off topic, or an order to the coach: say what the coach is for, without repeating the order.
REDIRECT: dict[ReportLanguage, str] = {
    "en": _say(
        "I can only help you plan your money before you leave.",
        "Please answer my last question when you are ready.",
    ),
    "hi": _say(
        "यहाँ सिर्फ़ विदेश जाने से पहले आपकी पैसों की योजना पर बात हो सकती है।",
        "जब आप तैयार हों, कृपया मेरे पिछले सवाल का जवाब दें।",
    ),
    "tl": _say(
        "Ang matutulungan ko lang ay ang pagpaplano ng pera mo bago ka umalis.",
        "Sagutin mo po ang huling tanong ko kapag handa ka na.",
    ),
    "id": _say(
        "Saya hanya bisa membantu merencanakan uang Anda sebelum berangkat.",
        "Silakan jawab pertanyaan saya yang terakhir kalau Anda sudah siap.",
    ),
    "ne": _say(
        "म तपाईंलाई जानुअघि पैसाको योजना बनाउन मात्र मद्दत गर्न सक्छु।",
        "तयार भएपछि कृपया मेरो अघिल्लो प्रश्नको जवाफ दिनुहोस्।",
    ),
    "bn": _say(
        "আমি শুধু যাওয়ার আগে আপনার টাকার পরিকল্পনায় সাহায্য করতে পারি।",
        "প্রস্তুত হলে অনুগ্রহ করে আমার আগের প্রশ্নের উত্তর দিন।",
    ),
}

# A request to choose a loan, an investment, an app or a company.
PRODUCT: dict[ReportLanguage, str] = {
    "en": _say("I cannot recommend loans, investments, apps or companies.", REDIRECT["en"]),
    "hi": _say("लोन, निवेश, ऐप या कंपनी की सलाह देना मेरे लिए संभव नहीं है।", REDIRECT["hi"]),
    "tl": _say("Hindi ako makapagrerekomenda ng loan, investment, app o kompanya.", REDIRECT["tl"]),
    "id": _say(
        "Saya tidak bisa merekomendasikan pinjaman, investasi, aplikasi, atau perusahaan.",
        REDIRECT["id"],
    ),
    "ne": _say("म ऋण, लगानी, एप वा कम्पनीको सिफारिस गर्न सक्दिनँ।", REDIRECT["ne"]),
    "bn": _say("আমি ঋণ, বিনিয়োগ, অ্যাপ বা কোম্পানির পরামর্শ দিতে পারি না।", REDIRECT["bn"]),
}

# Distress: sorry, who to turn to, danger now, and the way back to the interview if they want it.
REFERRAL: dict[ReportLanguage, str] = {
    "en": _say(
        "I am sorry you are going through this.",
        "You do not have to face it alone.",
        "Please talk to someone you trust.",
        "You can also contact your embassy or consulate, or a support group for migrant workers.",
        "If you are in danger now, call the local emergency number.",
        "When you feel ready, we can go back to your money plan.",
    ),
    "hi": _say(
        "आपके साथ जो हो रहा है, उसके लिए मुझे खेद है।",
        "आपको यह अकेले नहीं सहना है।",
        "कृपया किसी भरोसेमंद व्यक्ति से बात करें।",
        "आप अपने दूतावास या वाणिज्य दूतावास, या प्रवासी मज़दूरों की सहायता करने वाली संस्था से भी "
        "संपर्क कर सकते हैं।",
        "अगर आप अभी खतरे में हैं, तो वहाँ का आपातकालीन नंबर मिलाएँ।",
        "जब आप तैयार हों, हम आपकी पैसों की योजना पर लौट सकते हैं।",
    ),
    "tl": _say(
        "Pasensya na sa pinagdadaanan mo.",
        "Hindi mo kailangang harapin ito nang mag-isa.",
        "Makipag-usap ka po sa taong pinagkakatiwalaan mo.",
        "Maaari ka ring makipag-ugnayan sa embahada o konsulado ng bansa mo, "
        "o sa grupong tumutulong sa mga migranteng manggagawa.",
        "Kung nasa panganib ka ngayon, tawagan ang local emergency number.",
        "Kapag handa ka na, maaari tayong bumalik sa plano mo sa pera.",
    ),
    "id": _say(
        "Saya turut prihatin dengan apa yang Anda alami.",
        "Anda tidak harus menghadapinya sendiri.",
        "Bicaralah dengan orang yang Anda percaya.",
        "Anda juga bisa menghubungi kedutaan atau konsulat negara Anda, "
        "atau kelompok pendukung pekerja migran.",
        "Jika Anda dalam bahaya sekarang, hubungi nomor darurat setempat.",
        "Kalau sudah siap, kita bisa kembali ke rencana uang Anda.",
    ),
    "ne": _say(
        "तपाईंले भोगिरहनुभएकोमा मलाई दुःख लाग्छ।",
        "तपाईंले यो एक्लै सामना गर्नुपर्दैन।",
        "कृपया आफ्नो विश्वासिलो व्यक्तिसँग कुरा गर्नुहोस्।",
        "तपाईं आफ्नो देशको दूतावास वा वाणिज्य दूतावास, वा आप्रवासी कामदारलाई सहयोग गर्ने "
        "संस्थासँग पनि सम्पर्क गर्न सक्नुहुन्छ।",
        "यदि तपाईं अहिले खतरामा हुनुहुन्छ भने, स्थानीय आपतकालीन नम्बरमा फोन गर्नुहोस्।",
        "तयार हुँदा हामी तपाईंको पैसाको योजनामा फर्कन सक्छौँ।",
    ),
    "bn": _say(
        "আপনি যা সহ্য করছেন তার জন্য আমি দুঃখিত।",
        "আপনাকে এটা একা সামলাতে হবে না।",
        "অনুগ্রহ করে বিশ্বাসযোগ্য কারও সাথে কথা বলুন।",
        "আপনি আপনার দেশের দূতাবাস বা কনস্যুলেটের সাথে, অথবা প্রবাসী শ্রমিকদের সহায়তাকারী "
        "সংগঠনের সাথেও যোগাযোগ করতে পারেন।",
        "আপনি এখন বিপদে থাকলে স্থানীয় জরুরি নম্বরে ফোন করুন।",
        "প্রস্তুত হলে আমরা আপনার টাকার পরিকল্পনায় ফিরে যেতে পারি।",
    ),
}

# The note on every plan and its PDF (design 4.5). The plan carries it in the worker's language
# exactly as written here, never as a model's translation of it.
NOT_ADVICE_NOTE: dict[ReportLanguage, str] = {
    "en": _say(
        "This plan is a guide to help you think ahead.",
        "It is not professional financial advice.",
        "Check important decisions with a trusted adviser or a worker support organisation.",
    ),
    "hi": _say(
        "यह योजना आगे की सोचने में मदद करने वाली एक गाइड है।",
        "यह पेशेवर वित्तीय सलाह नहीं है।",
        "ज़रूरी फ़ैसले किसी भरोसेमंद सलाहकार या प्रवासी मज़दूरों की सहायता संस्था से जाँच लें।",
    ),
    "tl": _say(
        "Gabay lang ang planong ito para makapag-isip ka nang maaga.",
        "Hindi ito propesyonal na payong pinansyal.",
        "Ipasuri ang mahahalagang desisyon sa pinagkakatiwalaang tagapayo o sa organisasyong "
        "tumutulong sa mga manggagawa.",
    ),
    "id": _say(
        "Rencana ini hanya panduan untuk membantu Anda berpikir ke depan.",
        "Ini bukan nasihat keuangan profesional.",
        "Periksakan keputusan penting kepada penasihat tepercaya atau organisasi pendukung "
        "pekerja.",
    ),
    "ne": _say(
        "यो योजना अगाडिको बारेमा सोच्न मद्दत गर्ने मार्गदर्शन मात्र हो।",
        "यो व्यावसायिक वित्तीय सल्लाह होइन।",
        "महत्त्वपूर्ण निर्णयहरू भरपर्दो सल्लाहकार वा कामदार सहयोग संस्थासँग जाँच गर्नुहोस्।",
    ),
    "bn": _say(
        "এই পরিকল্পনা আগে থেকে ভাবতে সাহায্য করার একটি নির্দেশিকা মাত্র।",
        "এটি পেশাদার আর্থিক পরামর্শ নয়।",
        "গুরুত্বপূর্ণ সিদ্ধান্ত বিশ্বস্ত পরামর্শদাতা বা শ্রমিক সহায়তা সংগঠনের সাথে যাচাই করুন।",
    ),
}


def reply_for(decision: GuardDecision, language: ReportLanguage) -> str:
    """The fixed reply to a turn the guard blocked."""
    if decision.action == "refer":
        return REFERRAL[language]
    if decision.reason.startswith("product_request"):
        return PRODUCT[language]
    return REDIRECT[language]
