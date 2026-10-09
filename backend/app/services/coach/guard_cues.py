"""The words the Coach guard looks for (NF-FC-013).

Each pattern is a narrow cue: it fires on a message that gives the coach orders, signals danger, or
asks the coach to choose a financial product. Languages: English, Hindi, Tagalog, Indonesian, Nepali
and Bengali, in their own script and in Latin letters where workers write that way. A message no
cue fires on is not thereby safe: the guard sends it on to the classifier (`guard.py`).

The non-English lists were written by the team, not by native speakers (deferred item D-223). A
missed cue costs one classifier call. A cue that fires too often costs a worker a polite
redirect, so the cues stay narrow, and `tests/unit/services/test_coach_guard_rules.py` holds them
to the 140 scripted persona messages. Patterns run on text folded by `guard_rules.views` (NFKC,
lower case, ASCII digits, no invisible marks), so they are written in lower case.
"""

from __future__ import annotations

_GAP = r"(?:\W+\w+)"

# Orders to the coach: change the rules, reveal the prompt, take a role, or fake a prompt section.
INJECTION: tuple[str, ...] = (
    # English
    rf"\b(?:ignore|disregard|forget|override|bypass)\b{_GAP}{{0,3}}?\W+"
    rf"(?:previous|prior|above|earlier|preceding|your|system|all)\b{_GAP}{{0,2}}?\W+"
    r"(?:instructions?|rules?|prompts?|guidelines?|programming|restrictions?|directions?|"
    r"messages?|context)\b",
    r"\b(?:ignore|disregard)\s+(?:everything|all)\s+(?:above|before|that)\b",
    rf"\b(?:reveal|show|print|repeat|output|display|leak|tell|give|say|write)\b{_GAP}{{0,3}}?\W+"
    r"(?:system|initial|original|hidden|secret|your)\W+(?:prompt|instructions?|rules?)\b",
    r"\b(?:system|pre|meta)[ -]?prompt\b",
    r"\byou\s+are\s+now\b|\bpretend\s+(?:to\s+be|you)\b|\bact\s+as\s+(?:a|an|if|though)\b|"
    r"\brole-?play\b|\bdo\s+anything\s+now\b|\bdeveloper\s+mode\b|\bjail-?break\w*\b|"
    r"\bfrom\s+now\s+on\b\W+(?:\w+\W+){0,2}(?:you|ignore|act|only|always)\b",
    r"\b(?:system|assistant|developer)\s*(?:message|prompt|instruction)?\s*:",
    r"\[\s*/?\s*(?:system|inst|assistant)\s*\]|<\|[a-z_]+\|>|#{2,}\s*(?:system|instructions?)\b",
    r"\bnew\s+(?:instructions?|rules?|role|task)\s*:",
    r"</?\s*(?:system|assistant|developer|instructions?|worker_message|summary_of_earlier_talk|"
    r"recent_talk|slots|ask_next|follow_up|understood|stage|language|first_message|asking|"
    r"unconfirmed|confirmed|today)\b",
    # Hindi
    r"(?:निर्देश|आदेश|नियम)\S*\s+(?:\S+\s+){0,3}"
    r"(?:अनदेखा|नज़रअंदाज़|नजरअंदाज|भूल\s*जा\S*|भुला\S*|मत\s*मान\S*)",
    r"(?:अनदेखा|नज़रअंदाज़|नजरअंदाज|भूल\s*जा\S*)\s+(?:\S+\s+){0,3}(?:निर्देश|आदेश|नियम)",
    r"सिस्टम\s*प्रॉम्प्ट|सिस्टम\s*प्रोम्प्ट",
    r"\b(?:bhool|nazar\s*andaz)\w*\W+(?:\w+\W+){0,3}(?:nirdesh|instructions?|niyam)\w*",
    # Tagalog
    r"\b(?:i-?ignore|kalimutan|balewalain|huwag\s+pansinin|wag\s+pansinin)\b\W+(?:\w+\W+){0,6}"
    r"(?:utos|tagubilin|instruksyon|instructions?|patakaran|alituntunin)\b",
    # Indonesian
    r"\b(?:abaikan|lupakan|kesampingkan|acuhkan)\b\W+(?:\w+\W+){0,6}"
    r"(?:instruksi|perintah|aturan|petunjuk|arahan|prompt)\b",
    r"\b(?:prompt|instruksi)\s+sistem\b|\b(?:kamu|anda)\s+sekarang\s+(?:adalah|jadi)\b",
    r"\b(?:tunjukkan|tampilkan|ungkapkan|bocorkan)\b\W+(?:\w+\W+){0,3}(?:prompt|instruksi)\b",
    # Nepali
    r"(?:निर्देशन|निर्देश|आदेश|नियम)\S*\s+(?:\S+\s+){0,3}(?:बेवास्ता|बिर्स\S*|नमान\S*|अनदेखा)",
    r"(?:बेवास्ता|बिर्स\S*)\s+(?:गर\S*\s+)?(?:\S+\s+){0,3}(?:निर्देशन|निर्देश|आदेश|नियम)",
    r"सिस्टम\s*प्रम्प्ट",
    # Bengali
    r"(?:নির্দেশনা|নির্দেশ|নিয়ম|আদেশ)\S*\s+(?:\S+\s+){0,3}"
    r"(?:উপেক্ষা|ভুলে\s*যাও|ভুলে\s*যান|অগ্রাহ্য|মানবে\s*না)",
    r"(?:উপেক্ষা|ভুলে\s*যাও|অগ্রাহ্য)\s*(?:কর\S*\s+)?(?:\S+\s+){0,3}"
    r"(?:নির্দেশনা|নির্দেশ|নিয়ম|আদেশ)",
    r"সিস্টেম\s*প্রম্পট|সিস্টেম\s*প্রোম্পট",
)

# The same attacks with the letters run together (`i.g.n.o.r.e`, `ignore_previous_instructions`),
# tested on the text with everything but letters and digits taken out.
SQUEEZED_ORDERS: tuple[str, ...] = (
    "ignorepreviousinstructions",
    "ignoreallprevious",
    "ignoreyourinstructions",
    "ignoreyourrules",
    "ignoretheabove",
    "disregardprevious",
    "disregardallprevious",
    "forgetyourinstructions",
    "forgetallprevious",
    "forgetpreviousinstructions",
    "overrideyourinstructions",
    "revealyoursystemprompt",
    "showyoursystemprompt",
    "printyoursystemprompt",
    "systemprompt",
    "doanythingnow",
    "developermode",
)

# Danger to the worker or someone close. Checked before everything else: a referral to a false
# alarm costs one kind message, a missed one costs far more.
DISTRESS: tuple[str, ...] = (
    # English
    r"\b(?:kill(?:ing)?\s+myself|end(?:ing)?\s+my\s+(?:own\s+)?life|take\s+my\s+(?:own\s+)?life|"
    r"want\s+to\s+die|wish\s+i\s+(?:was|were)\s+dead|suicid\w*|self[- ]?harm\w*|"
    r"hurt(?:ing)?\s+myself|don'?t\s+want\s+to\s+(?:live|be\s+alive))\b",
    r"\b(?:rap(?:e|ed|ing)|sexual(?:ly)?\s+(?:assault|abus)\w*)\b",
    r"\b(?:beat|beats|beating|beaten|hit|hits|hitting|slap\w*|punch\w*|kick\w*|abus\w*|"
    r"assault\w*|torture\w*|threaten\w*)\s+(?:me|us)\b",
    r"\b(?:took|taken|takes|kept|keeps|holding|holds|confiscat\w*|withh\w+|seiz\w*)\b"
    r"(?:\W+\w+){0,6}?\W+(?:passports?|documents|papers)\b",
    r"\bpassports?\b(?:\W+\w+){0,6}?\W+(?:taken|kept|confiscated|withheld|locked|seized)\b",
    r"\b(?:locked\s+(?:me\s+)?(?:in|up)|not\s+allowed\s+to\s+leave|trapped|"
    r"held\s+against\s+my\s+will|forced\s+(?:me\s+)?to\s+work|forced\s+labou?r|slave\w*|"
    r"traffick\w*|bonded\s+labou?r|debt\s+bondage|"
    r"can(?:'?t|not)\s+leave\s+(?:the|this|my)\s+(?:house|room|place|dorm|compound|workplace))\b",
    r"\b(?:no\s+food|starv\w+|in\s+danger|(?:fear|afraid|scared)\s+for\s+my\s+(?:life|safety))\b",
    # Hindi
    r"आत्महत्या|आत्म-हत्या|मरना\s+चाहत\S*|जान\s+दे\s+दू\S*",
    r"पासपोर्ट\s+(?:\S+\s+){0,4}(?:छीन\S*|ज़ब्त\S*|जब्त\S*|रख\s*ल\S*|रख\s*लिया)",
    r"(?:छीन\S*|ज़ब्त\S*|जब्त\S*)\s+(?:\S+\s+){0,4}पासपोर्ट",
    r"मारपीट|पीटत\S*|पीटा|बलात्कार|बंधक|जबरन\s+(?:काम|मज़दूरी|मजदूरी)|खतरे\s+में",
    # Tagalog
    r"\b(?:magpakamatay|pagpapakamatay|gusto\s+ko\s+nang\s+mamatay|ayoko\s+nang\s+mabuhay)\b",
    r"\bpasaporte\b\W+(?:\w+\W+){0,5}(?:kinuha|hawak|kinumpiska|itinago)\b",
    r"\b(?:kinuha|kinumpiska|hawak)\b\W+(?:\w+\W+){0,5}pasaporte\b",
    r"\b(?:sinasaktan|binubugbog|pinapalo|ginahasa|ikinulong|nakakulong|pinipilit\s+(?:akong\s+)?"
    r"magtrabaho|trafficked|human\s+trafficking)\b",
    # Indonesian
    r"\b(?:bunuh\s+diri|ingin\s+mati|mau\s+mati)\b",
    r"\bpaspor\b\W+(?:\w+\W+){0,5}(?:ditahan|disita|diambil|ditahan)\b",
    r"\b(?:ditahan|disita|diambil)\b\W+(?:\w+\W+){0,5}paspor\b",
    r"\b(?:dipukul|disiksa|dianiaya|diperkosa|pemerkosaan|disekap|dikurung|dipaksa\s+bekerja|"
    r"perdagangan\s+orang|diperdagangkan|tidak\s+boleh\s+keluar)\b",
    # Nepali
    r"आत्महत्या|मर्न\s+(?:मन\s+लाग्य\S*|चाहन्छु)",
    r"राहदानी\s+(?:\S+\s+){0,4}(?:खोस\S*|जफत\S*|राखे\S*)",
    r"(?:खोस\S*|जफत\S*)\s+(?:\S+\s+){0,4}राहदानी",
    r"कुटपिट|कुट्छ|कुटे\S*|बलात्कार|बन्धक|जबरजस्ती\s+काम|मानव\s+बेचबिखन",
    # Bengali
    r"আত্মহত্যা|মরে\s*যেতে\s*চাই|মরতে\s*চাই",
    r"পাসপোর্ট\s+(?:\S+\s+){0,4}(?:কেড়ে\S*|আটকে\S*|জব্দ\S*|রেখে\S*)",
    r"(?:কেড়ে\S*|আটকে\S*|জব্দ\S*)\s+(?:\S+\s+){0,4}পাসপোর্ট",
    r"মারধর|ধর্ষণ|বন্দী|জোর\s*করে\s*কাজ|মানব\s*পাচার",
)

# A request that the coach pick a loan, a lender, an investment, an app, a bank or a company, or
# lend money itself. A worker *telling* the coach about their own loan is an answer, not this.
_PRODUCT = (
    r"(?:loans?|lenders?|invest\w*|stocks?|shares|mutual\s+funds?|funds?|crypto\w*|bitcoin|"
    r"forex|trading|insurance|credit\s+cards?|fixed\s+deposits?|schemes?|apps?|compan(?:y|ies)|"
    r"brokers?|banks?)"
)
PRODUCT_REQUEST: tuple[str, ...] = (
    # English
    rf"\b(?:which|best|better|safest|cheapest|good|recommend\w*|suggest\w*|advise)\b{_GAP}{{0,5}}?"
    rf"\W+{_PRODUCT}\b",
    rf"\bshould\s+i\s+(?:take|get|apply|invest|borrow|buy|put|use|join|choose)\b{_GAP}{{0,5}}?"
    rf"\W+{_PRODUCT}\b",
    r"\bwhere\s+(?:to|should\s+i|can\s+i|do\s+i)\s+(?:invest|put\s+my|borrow|get\s+a\s+loan)\b",
    r"\b(?:lend|loan|give)\s+me\s+(?:some\s+)?(?:money|cash|a\s+loan)\b|\bcan\s+you\s+(?:lend|loan)\b",
    # Hindi
    r"कौन\s*(?:सा|सी)\s+(?:लोन|कर्ज|ऋण|ऐप|कंपनी|बीमा|बैंक|निवेश)",
    r"(?:कहाँ|कहां)\s+(?:पर\s+)?निवेश|निवेश\s+कहाँ|सबसे\s+(?:अच्छा|सस्ता|सुरक्षित)\s+"
    r"(?:लोन|ऐप|बैंक|निवेश|कंपनी)",
    # Tagalog
    r"\b(?:anong|aling|saang)\s+(?:loan|pautang|investment|app|kompanya|bangko|insurance)\b",
    r"\bsaan\s+(?:ako\s+)?(?:mag-?invest|mangutang|makakautang)\b|"
    r"\bmagandang\s+(?:investment|pautang|loan|app)\b",
    # Indonesian
    r"\b(?:pinjaman|investasi|aplikasi|asuransi|bank|perusahaan)\s+(?:apa|mana|terbaik|yang\s+bagus)\b",
    r"\bdi\s+mana\s+(?:saya\s+)?(?:harus\s+)?(?:investasi|meminjam)\b",
    # Nepali
    r"कुन\s+(?:ऋण|लोन|एप|कम्पनी|बैंक|बिमा)|(?:कहाँ|कता)\s+लगानी|लगानी\s+कहाँ",
    # Bengali
    r"কোন\s+(?:ঋণ|লোন|অ্যাপ|কোম্পানি|ব্যাংক|বিমা)|কোথায়\s+বিনিয়োগ|বিনিয়োগ\s+কোথায়",
)

# A reply that recommends a product. Much narrower than the input cues: the coach legitimately asks
# "Did you get a loan?" and "Do you have another loan?", so only a recommending phrase next to a
# product word counts, and companies are left out (the prompt and the input cues cover them).
_REPLY_PRODUCT = (
    r"(?:loans?|lenders?|invest\w*|stocks?|shares|funds?|crypto\w*|bitcoin|forex|insurance|"
    r"credit\s+cards?|schemes?|brokers?|apps?)"
)
REPLY_ADVICE: tuple[str, ...] = (
    # English
    rf"\b(?:i|we)\s+(?:strongly\s+)?(?:recommend|suggest|advise)\b{_GAP}{{0,8}}?\W+{_REPLY_PRODUCT}\b",
    r"\byou\s+(?:should|must|ought\s+to|need\s+to|had\s+better)\s+(?:\w+\s+){0,3}?"
    r"(?:take(?:\s+out)?|get|apply\s+for|borrow|invest|buy|open|use|try|join)\b"
    rf"{_GAP}{{0,5}}?\W+{_REPLY_PRODUCT}\b",
    r"\b(?:consider|explore|look\s+into)\s+(?:investing|a\s+(?:loan|lender)|crypto|bitcoin|"
    r"stocks|shares|mutual\s+funds?)\b",
    # Hindi
    r"निवेश\s+(?:\S+\s+){0,3}(?:करें|कीजिए|करना\s+चाहिए)",
    r"(?:शेयर|क्रिप्टो|बिटकॉइन)\s+(?:\S+\s+){0,3}(?:खरीद\S*|लें|लीजिए)",
    r"(?:नया|दूसरा)\s+(?:लोन|कर्ज)\s+(?:\S+\s+){0,2}(?:लें|लीजिए|ले\s+सकते)",
    # Tagalog
    r"\b(?:mag-?invest\s+ka|dapat\s+(?:kang\s+)?(?:mag-?invest|kumuha\s+ng\s+(?:bagong\s+)?loan)|"
    r"inirerekomenda\s+(?:ko\s+)?(?:ang\s+)?(?:investment|loan|app))\b",
    # Indonesian
    r"\b(?:sebaiknya|anda\s+harus|kamu\s+harus|saya\s+sarankan|disarankan)\b\W+(?:\w+\W+){0,6}"
    r"(?:berinvestasi|investasi|pinjaman|meminjam|saham|kripto|asuransi|aplikasi)\b",
    # Nepali
    r"लगानी\s+(?:\S+\s+){0,3}(?:गर्नुहोस्|गर्नुपर्छ)|(?:ऋण|लोन)\s+(?:\S+\s+){0,2}लिनुहोस्",
    # Bengali
    r"বিনিয়োগ\s+(?:\S+\s+){0,3}(?:করুন|করা\s+উচিত)|ঋণ\s+(?:\S+\s+){0,2}নিন",
)
