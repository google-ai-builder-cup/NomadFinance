"""Fixed wording of the Financial Identity PDF in the six app languages (NF-P3-014).

The report text itself is the profile's narrative, already in the worker's language; these
are the headings, metric names and the disclaimer around it. NOT yet reviewed by a native
speaker for hi, tl, id, ne and bn: have that done before a lender reads a real report.
"""

from __future__ import annotations

from typing import Final

LABEL_KEYS: Final = (
    "title",
    "prepared_for",
    "period",
    "months",
    "currency",
    "computed",
    "created",
    "records",
    "income_entries",
    "transfer_entries",
    "bill_entries",
    "savings_entries",
    "indicators",
    "score_of",
    "no_data",
    "summary",
    "verified_heading",
    "verified_employer",
    "verified_salary",
    "shared_heading",
    "shared_note",
    "coach_checkins",
    "coach_remittance",
    "coach_savings",
    "coach_pay",
    "coach_last",
    "coach_target",
    "coach_recorded",
    "scam_checks",
    "scam_found",
    "scam_last",
    "disclaimer",
    "income_stability",
    "savings_rate",
    "remittance_consistency",
    "bill_payment_reliability",
)

LABELS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "title": "Financial Identity Report",
        "prepared_for": "Prepared for",
        "period": "Period covered",
        "months": "Months of records",
        "currency": "Reporting currency",
        "computed": "Profile computed on",
        "created": "Report created on",
        "records": "Records used",
        "income_entries": "Income entries",
        "transfer_entries": "Transfers home",
        "bill_entries": "Bills",
        "savings_entries": "Savings entries",
        "indicators": "Indicators",
        "score_of": "out of 100",
        "no_data": "Not enough records",
        "summary": "Summary",
        "verified_heading": "Employment verified from a contract",
        "verified_employer": "Employer",
        "verified_salary": "Salary stated in the contract",
        "shared_heading": "Activity the worker chose to share",
        "shared_note": (
            "These are counts of what the worker did in NomadFinance. "
            "They include no message, answer or other text the worker wrote."
        ),
        "coach_checkins": "Plan check-ins answered (of 3)",
        "coach_remittance": "Check-ins where sending money home was on track",
        "coach_savings": "Check-ins where saving was on track",
        "coach_pay": "Check-ins where pay arrived in full and on time",
        "coach_last": "Last check-in answered on",
        "coach_target": "Savings rate the plan aimed for",
        "coach_recorded": "Savings rate recorded in this period",
        "scam_checks": "Messages checked for scams (last 90 days)",
        "scam_found": "Of these, flagged as likely scams",
        "scam_last": "Last message checked on",
        "disclaimer": (
            "This report is based on entries the worker recorded in NomadFinance and on the "
            "transfers they logged. Except for employment marked as verified from a contract, "
            "NomadFinance has not checked them against bank records. The scores describe "
            "recorded behaviour. They are not a credit score and not a recommendation to lend."
        ),
        "income_stability": "Income stability",
        "savings_rate": "Savings rate",
        "remittance_consistency": "Remittance consistency",
        "bill_payment_reliability": "Bill payment reliability",
    },
    "hi": {
        "title": "वित्तीय पहचान रिपोर्ट",
        "prepared_for": "इनके लिए तैयार",
        "period": "अवधि",
        "months": "रिकॉर्ड के महीने",
        "currency": "रिपोर्टिंग मुद्रा",
        "computed": "प्रोफ़ाइल की गणना की तारीख़",
        "created": "रिपोर्ट बनाने की तारीख़",
        "records": "उपयोग किए गए रिकॉर्ड",
        "income_entries": "आय की प्रविष्टियाँ",
        "transfer_entries": "घर भेजी गई रकम",
        "bill_entries": "बिल",
        "savings_entries": "बचत की प्रविष्टियाँ",
        "indicators": "संकेतक",
        "score_of": "100 में से",
        "no_data": "पर्याप्त रिकॉर्ड नहीं",
        "summary": "सारांश",
        "verified_heading": "अनुबंध से सत्यापित रोज़गार",
        "verified_employer": "नियोक्ता",
        "verified_salary": "अनुबंध में लिखा वेतन",
        "shared_heading": "कामगार द्वारा साझा की गई गतिविधि",
        "shared_note": (
            "ये NomadFinance में कामगार की गतिविधि की गिनती हैं। "
            "इनमें कामगार का लिखा कोई संदेश, जवाब या अन्य पाठ शामिल नहीं है।"
        ),
        "coach_checkins": "जवाब दिए गए योजना चेक-इन (3 में से)",
        "coach_remittance": "चेक-इन जिनमें घर पैसे भेजना योजना के अनुसार रहा",
        "coach_savings": "चेक-इन जिनमें बचत योजना के अनुसार रही",
        "coach_pay": "चेक-इन जिनमें वेतन पूरा और समय पर मिला",
        "coach_last": "आख़िरी चेक-इन का जवाब दिया गया",
        "coach_target": "योजना में तय बचत दर",
        "coach_recorded": "इस अवधि में दर्ज बचत दर",
        "scam_checks": "धोखाधड़ी के लिए जाँचे गए संदेश (पिछले 90 दिन)",
        "scam_found": "इनमें से संभावित धोखाधड़ी के रूप में चिह्नित",
        "scam_last": "आख़िरी संदेश जाँचा गया",
        "disclaimer": (
            "यह रिपोर्ट उन प्रविष्टियों पर आधारित है जो कामगार ने NomadFinance में दर्ज कीं और "
            "उन ट्रांसफ़र पर जो उन्होंने लॉग किए। अनुबंध से सत्यापित रोज़गार को छोड़कर, "
            "NomadFinance ने इन्हें बैंक रिकॉर्ड से नहीं मिलाया है। स्कोर दर्ज किए गए व्यवहार का "
            "वर्णन करते हैं। यह क्रेडिट स्कोर नहीं है और कर्ज़ देने की सिफ़ारिश भी नहीं है।"
        ),
        "income_stability": "आय की स्थिरता",
        "savings_rate": "बचत दर",
        "remittance_consistency": "घर पैसे भेजने की निरंतरता",
        "bill_payment_reliability": "बिल भुगतान की विश्वसनीयता",
    },
    "tl": {
        "title": "Ulat ng Pagkakakilanlang Pinansyal",
        "prepared_for": "Inihanda para kay/sa",
        "period": "Saklaw na panahon",
        "months": "Buwan ng mga tala",
        "currency": "Pera ng ulat",
        "computed": "Petsa ng pagkalkula ng profile",
        "created": "Petsa ng paggawa ng ulat",
        "records": "Mga tala na ginamit",
        "income_entries": "Mga tala ng kita",
        "transfer_entries": "Mga padala sa pamilya",
        "bill_entries": "Mga bill",
        "savings_entries": "Mga tala ng ipon",
        "indicators": "Mga indikasyon",
        "score_of": "mula sa 100",
        "no_data": "Kulang ang mga tala",
        "summary": "Buod",
        "verified_heading": "Trabahong napatunayan mula sa kontrata",
        "verified_employer": "Employer",
        "verified_salary": "Sahod ayon sa kontrata",
        "shared_heading": "Aktibidad na piniling ibahagi ng manggagawa",
        "shared_note": (
            "Mga bilang ito ng ginawa ng manggagawa sa NomadFinance. Walang "
            "kasamang mensahe, sagot o iba pang tekstong isinulat ng manggagawa."
        ),
        "coach_checkins": "Mga check-in ng plano na nasagot (sa 3)",
        "coach_remittance": "Mga check-in na nasa takbo ang pagpapadala ng pera sa pamilya",
        "coach_savings": "Mga check-in na nasa takbo ang pag-iipon",
        "coach_pay": "Mga check-in na buo at nasa oras ang sahod",
        "coach_last": "Huling check-in na nasagot noong",
        "coach_target": "Rate ng pag-iipon na target ng plano",
        "coach_recorded": "Rate ng pag-iipon na naitala sa panahong ito",
        "scam_checks": "Mga mensaheng sinuri para sa scam (huling 90 araw)",
        "scam_found": "Sa mga ito, minarkahang posibleng scam",
        "scam_last": "Huling mensaheng sinuri noong",
        "disclaimer": (
            "Batay ang ulat na ito sa mga tala na inilagay ng manggagawa sa NomadFinance at sa "
            "mga padalang kanyang itinala. Maliban sa trabahong napatunayan mula sa kontrata, "
            "hindi ito ikinumpara ng NomadFinance sa mga tala ng bangko. Inilalarawan ng mga "
            "marka ang naitalang gawi. Hindi ito credit score at hindi rin rekomendasyon na "
            "magpautang."
        ),
        "income_stability": "Katatagan ng kita",
        "savings_rate": "Antas ng pag-iipon",
        "remittance_consistency": "Pagkakapare-pareho ng pagpapadala ng pera",
        "bill_payment_reliability": "Pagiging maaasahan sa pagbabayad ng bill",
    },
    "id": {
        "title": "Laporan Identitas Keuangan",
        "prepared_for": "Disiapkan untuk",
        "period": "Periode",
        "months": "Jumlah bulan catatan",
        "currency": "Mata uang laporan",
        "computed": "Tanggal profil dihitung",
        "created": "Tanggal laporan dibuat",
        "records": "Catatan yang digunakan",
        "income_entries": "Catatan pendapatan",
        "transfer_entries": "Kiriman uang ke rumah",
        "bill_entries": "Tagihan",
        "savings_entries": "Catatan tabungan",
        "indicators": "Indikator",
        "score_of": "dari 100",
        "no_data": "Catatan belum cukup",
        "summary": "Ringkasan",
        "verified_heading": "Pekerjaan terverifikasi dari kontrak",
        "verified_employer": "Pemberi kerja",
        "verified_salary": "Gaji yang tertulis di kontrak",
        "shared_heading": "Aktivitas yang dipilih pekerja untuk dibagikan",
        "shared_note": (
            "Ini adalah jumlah kegiatan pekerja di NomadFinance. "
            "Tidak ada pesan, jawaban, atau teks lain yang ditulis pekerja."
        ),
        "coach_checkins": "Check-in rencana yang dijawab (dari 3)",
        "coach_remittance": "Check-in dengan pengiriman uang sesuai rencana",
        "coach_savings": "Check-in dengan tabungan sesuai rencana",
        "coach_pay": "Check-in dengan gaji diterima penuh dan tepat waktu",
        "coach_last": "Check-in terakhir dijawab pada",
        "coach_target": "Tingkat tabungan yang ditargetkan rencana",
        "coach_recorded": "Tingkat tabungan tercatat pada periode ini",
        "scam_checks": "Pesan yang diperiksa untuk penipuan (90 hari terakhir)",
        "scam_found": "Dari jumlah itu, ditandai sebagai kemungkinan penipuan",
        "scam_last": "Pesan terakhir diperiksa pada",
        "disclaimer": (
            "Laporan ini didasarkan pada catatan yang dimasukkan pekerja di NomadFinance dan "
            "pengiriman uang yang dicatatnya. Kecuali pekerjaan yang terverifikasi dari kontrak, "
            "NomadFinance belum mencocokkannya dengan catatan bank. Skor menggambarkan perilaku "
            "yang tercatat. Ini bukan skor kredit dan bukan rekomendasi untuk memberi pinjaman."
        ),
        "income_stability": "Stabilitas pendapatan",
        "savings_rate": "Rasio tabungan",
        "remittance_consistency": "Konsistensi pengiriman uang",
        "bill_payment_reliability": "Keandalan pembayaran tagihan",
    },
    "ne": {
        "title": "वित्तीय परिचय प्रतिवेदन",
        "prepared_for": "यसका लागि तयार पारिएको",
        "period": "अवधि",
        "months": "अभिलेखका महिना",
        "currency": "प्रतिवेदन मुद्रा",
        "computed": "प्रोफाइल गणना गरिएको मिति",
        "created": "प्रतिवेदन बनाइएको मिति",
        "records": "प्रयोग गरिएका अभिलेख",
        "income_entries": "आम्दानीका अभिलेख",
        "transfer_entries": "घर पठाइएको रकम",
        "bill_entries": "बिल",
        "savings_entries": "बचतका अभिलेख",
        "indicators": "सूचकहरू",
        "score_of": "100 मध्ये",
        "no_data": "पर्याप्त अभिलेख छैन",
        "summary": "सारांश",
        "verified_heading": "सम्झौताबाट प्रमाणित रोजगारी",
        "verified_employer": "रोजगारदाता",
        "verified_salary": "सम्झौतामा उल्लेख गरिएको तलब",
        "shared_heading": "कामदारले साझा गर्न रोजेको गतिविधि",
        "shared_note": (
            "यी NomadFinance मा कामदारले गरेका कामको गणना हुन्। यसमा "
            "कामदारले लेखेको कुनै सन्देश, जवाफ वा अन्य पाठ समावेश छैन।"
        ),
        "coach_checkins": "जवाफ दिइएका योजना चेक-इन (3 मध्ये)",
        "coach_remittance": "घरमा पैसा पठाउने काम योजनाअनुसार भएका चेक-इन",
        "coach_savings": "बचत योजनाअनुसार भएका चेक-इन",
        "coach_pay": "तलब पूरा र समयमै आएका चेक-इन",
        "coach_last": "अन्तिम चेक-इनको जवाफ दिइएको मिति",
        "coach_target": "योजनाले लक्ष्य राखेको बचत दर",
        "coach_recorded": "यस अवधिमा अभिलेख गरिएको बचत दर",
        "scam_checks": "ठगीका लागि जाँचिएका सन्देश (पछिल्लो 90 दिन)",
        "scam_found": "यीमध्ये सम्भावित ठगीका रूपमा चिनो लगाइएका",
        "scam_last": "अन्तिम सन्देश जाँचिएको मिति",
        "disclaimer": (
            "यो प्रतिवेदन कामदारले NomadFinance मा दर्ता गरेका अभिलेख र आफूले लग गरेका रकम "
            "पठाइमा आधारित छ। सम्झौताबाट प्रमाणित रोजगारी बाहेक, NomadFinance ले यिनलाई बैंक "
            "अभिलेखसँग मिलान गरेको छैन। अङ्कहरूले दर्ता गरिएको व्यवहार वर्णन गर्छन्। यो क्रेडिट "
            "स्कोर होइन र ऋण दिन गरिएको सिफारिस पनि होइन।"
        ),
        "income_stability": "आम्दानीको स्थिरता",
        "savings_rate": "बचत दर",
        "remittance_consistency": "घर पैसा पठाउने निरन्तरता",
        "bill_payment_reliability": "बिल भुक्तानीको विश्वसनीयता",
    },
    "bn": {
        "title": "আর্থিক পরিচয় প্রতিবেদন",
        "prepared_for": "যার জন্য তৈরি",
        "period": "সময়কাল",
        "months": "রেকর্ডের মাস",
        "currency": "প্রতিবেদনের মুদ্রা",
        "computed": "প্রোফাইল হিসাব করার তারিখ",
        "created": "প্রতিবেদন তৈরির তারিখ",
        "records": "ব্যবহৃত রেকর্ড",
        "income_entries": "আয়ের এন্ট্রি",
        "transfer_entries": "দেশে পাঠানো টাকা",
        "bill_entries": "বিল",
        "savings_entries": "সঞ্চয়ের এন্ট্রি",
        "indicators": "সূচক",
        "score_of": "100-এর মধ্যে",
        "no_data": "পর্যাপ্ত রেকর্ড নেই",
        "summary": "সারসংক্ষেপ",
        "verified_heading": "চুক্তি থেকে যাচাই করা কর্মসংস্থান",
        "verified_employer": "নিয়োগকর্তা",
        "verified_salary": "চুক্তিতে উল্লেখ করা বেতন",
        "shared_heading": "কর্মী যে কার্যকলাপ শেয়ার করতে বেছে নিয়েছেন",
        "shared_note": (
            "এগুলো NomadFinance-এ কর্মীর কাজের গণনা। এতে "
            "কর্মীর লেখা কোনো বার্তা, উত্তর বা অন্য লেখা নেই।"
        ),
        "coach_checkins": "উত্তর দেওয়া পরিকল্পনার চেক-ইন (3টির মধ্যে)",
        "coach_remittance": "যেসব চেক-ইনে দেশে টাকা পাঠানো পরিকল্পনা অনুযায়ী ছিল",
        "coach_savings": "যেসব চেক-ইনে সঞ্চয় পরিকল্পনা অনুযায়ী ছিল",
        "coach_pay": "যেসব চেক-ইনে বেতন পুরো এবং সময়মতো এসেছে",
        "coach_last": "সর্বশেষ চেক-ইনের উত্তর দেওয়া হয়েছে",
        "coach_target": "পরিকল্পনায় লক্ষ্য করা সঞ্চয়ের হার",
        "coach_recorded": "এই সময়ে রেকর্ড করা সঞ্চয়ের হার",
        "scam_checks": "প্রতারণার জন্য যাচাই করা বার্তা (গত 90 দিন)",
        "scam_found": "এর মধ্যে সম্ভাব্য প্রতারণা হিসেবে চিহ্নিত",
        "scam_last": "সর্বশেষ বার্তা যাচাই করা হয়েছে",
        "disclaimer": (
            "এই প্রতিবেদন কর্মী NomadFinance-এ যে এন্ট্রি দিয়েছেন এবং যে ট্রান্সফার লগ করেছেন "
            "তার ওপর ভিত্তি করে। চুক্তি থেকে যাচাই করা কর্মসংস্থান ছাড়া NomadFinance এগুলো "
            "ব্যাংক রেকর্ডের সঙ্গে মেলায়নি। স্কোরগুলো রেকর্ড করা আচরণ বর্ণনা করে। এটি ক্রেডিট "
            "স্কোর নয় এবং ঋণ দেওয়ার সুপারিশও নয়।"
        ),
        "income_stability": "আয়ের স্থিতিশীলতা",
        "savings_rate": "সঞ্চয়ের হার",
        "remittance_consistency": "দেশে টাকা পাঠানোর ধারাবাহিকতা",
        "bill_payment_reliability": "বিল পরিশোধের নির্ভরযোগ্যতা",
    },
}
