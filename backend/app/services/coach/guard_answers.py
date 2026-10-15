"""What makes a message look like an answer to an interview question (NF-FC-013).

This is the rules' way of letting an ordinary answer through with no model call. It is a cheap
shape test, not a judgement: a message that does not look like an answer costs one classifier
call, never a refusal. Languages: English, Hindi, Tagalog, Indonesian, Nepali and Bengali, written
by the team and not read by native speakers yet.
"""

from __future__ import annotations

import re

# Whole words that are themselves a reply (yes, no, thanks, hello, not yet), counted only in a
# message of at most four words so that "I do not know what to do anymore" is not one.
ACK_WORDS = frozenset(
    "yes yeah yep yup no nope ok okay sure correct right wrong thanks thank hi hello hey maybe "
    "later none nothing haan han nahi nahin theek sahi galat shukriya dhanyavad namaste "
    "हाँ हां जी नहीं नही ठीक सही गलत धन्यवाद शुक्रिया नमस्ते "
    "oo opo hindi tama mali salamat kumusta wala ewan baka mamaya "
    "ya iya tidak bukan benar betul salah terima makasih halo hai mungkin nanti belum "
    "हो होइन छैन सायद पछि ho hoina dhanyabad "
    "হ্যাঁ না ঠিক সঠিক ভুল ধন্যবাদ নমস্কার হ্যালো হয়তো পরে নেই".split()
)
ACK_PHRASES = (
    "not sure",
    "don't know",
    "dont know",
    "do not know",
    "no idea",
    "thank you",
    "pata nahi",
    "पता नहीं",
    "hindi ko alam",
    "ewan ko",
    "tidak tahu",
    "gak tahu",
    "nggak tahu",
    "थाहा छैन",
    "জানি না",
)

# Whole words that answer the job or the bank-or-wallet question without a number.
ANSWER_WORDS = frozenset(
    "domestic maid helper nurse caregiver carer care factory manufacturing construction "
    "plantation farm cleaner driver cook welder hotel restaurant engineer technician waiter "
    "housekeeper nanny babysitter bank account wallet gcash maya paymaya bkash esewa khalti "
    "paytm upi cash savings "
    "घरेलू नौकरानी नर्स फैक्ट्री फैक्टरी निर्माण बैंक खाता वॉलेट "
    "katulong kasambahay nars pabrika konstruksyon bangko pitaka taniman "
    "pembantu perawat pabrik konstruksi bangunan kebun sawit rekening dompet tki "
    "घरेलु कारखाना "
    "গৃহকর্মী নার্স কারখানা নির্মাণ ব্যাংক অ্যাকাউন্ট ওয়ালেট".split()
)

# Names only: a bare two-letter code ("my", "au") is an ordinary word and proves nothing.
COUNTRY_WORDS = re.compile(
    r"singapore|singapura|singapur|सिंगापुर|सिङ्गापुर|সিঙ্গাপুর|korea|कोरिया|কোরিয়া|seoul|"
    r"malaysia|मलेशिया|मलेसिया|মালয়েশিয়া|kuala lumpur|japan|jepang|जापान|জাপান|tokyo|osaka|"
    r"hong ?kong|हांगकांग|हङकङ|হংকং|australia|ऑस्ट्रेलिया|अस्ट्रेलिया|অস্ট্রেলিয়া|sydney|melbourne"
)

# Meta talk and requests to the coach. Even an answer-shaped message that holds one is sent to the
# classifier: "my salary is 2000 and write me a poem" is not an answer.
WEAK_SIGNALS = re.compile(
    r"\b(?:instructions?|prompts?|system|rules?|roles?|pretend|assistant|chatbot|gemini|openai|"
    r"google|developer|admin|override|bypass|password|secret|api ?key|respond|"
    r"reply with|output|you must|your (?:job|task|purpose|goal|name)|translate|repeat|print|"
    r"write|essay|poem|story|joke|song|recipe|code|script|weather|news|cricket|football|soccer|"
    r"movie|film|politic\w*|president|election|religion|horoscope|lottery|explain|bot|"
    r"(?:can|could|will|would) you|who (?:is|was|will)|why (?:is|are|do|does)|"
    r"tell me (?:a|about|who|what|how|why|when|where)|instruksi|aturan|perintah|utos|"
    r"tagubilin|patakaran|abaikan|lupakan)\b"
    r"|निर्देश|नियम|सिस्टम|प्रॉम्प्ट|নির্দেশ|নিয়ম|সিস্টেম|প্রম্পট"
)
