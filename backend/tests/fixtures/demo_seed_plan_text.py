# ruff: noqa: E501  (a table of sentences: a line is a sentence)
"""The words of the demo workers' 90-day plans, in English, Hindi and Tagalog (NF-HR-003).

Figures never come from here: `plan_text` receives the facts the plan was built from and writes
them into fixed sentences, so a sentence cannot disagree with its figure, and the backend's own
checks (`check_text`, the translation check) accept the result. Written by the team, not by a
native speaker (D-221).
"""

from __future__ import annotations

from typing import Any

from app.schemas.coach_plan_text import NoteText, PlanText, PlanTranslation, WeekText
from app.services.coach.guard_texts import NOT_ADVICE_NOTE

LANGUAGES = ("en", "hi", "tl")

# One entry per week: (title, [action, action]). No digit anywhere, so a translation has no
# number to keep and the validator has none to question.
WEEKS: dict[str, list[tuple[str, list[str]]]] = {
    "en": [
        (
            "Arrive and settle in",
            [
                "Keep your passport and contract with you, not with anyone else.",
                "Save the helpline numbers in your phone.",
            ],
        ),
        (
            "Set up your money",
            [
                "Check that you have an account your employer can pay into.",
                "Write down every cost, even small ones.",
            ],
        ),
        (
            "Know your contract",
            [
                "Read your contract again with someone you trust.",
                "Note your pay day and what is taken from your pay.",
            ],
        ),
        ("Your first pay", ["Check that your pay matches your contract.", "Keep the payslip."]),
        (
            "Send money home",
            ["Compare services before you send.", "Send the planned amount and keep the receipt."],
        ),
        (
            "Check your spending",
            ["Compare what you spent with the plan.", "Cut one cost if money is short."],
        ),
        (
            "Keep to your goals",
            [
                "Set aside what the plan says for each goal.",
                "Do not skip a goal because one month felt hard.",
            ],
        ),
        (
            "Build your safety money",
            [
                "Put aside the amount the plan sets for emergencies.",
                "Keep it where you can reach it quickly.",
            ],
        ),
        (
            "Send money home again",
            ["Compare services again, because prices change.", "Keep every receipt."],
        ),
        (
            "Check your papers",
            [
                "Make copies of your documents and keep them safe.",
                "Check when your permit and passport expire.",
            ],
        ),
        (
            "Talk to someone you trust",
            [
                "If pay or work is not as promised, talk to a worker support group early.",
                "Do not wait until the problem is big.",
            ],
        ),
        (
            "Plan the next month",
            ["Update the plan with what you really spent.", "Decide what you will change."],
        ),
        (
            "Look back",
            [
                "Send the planned amount home and keep the receipt.",
                "Look back over these three months: what worked and what did not.",
            ],
        ),
    ],
    "hi": [
        (
            "पहुँचें और बस जाएँ",
            [
                "अपना पासपोर्ट और अनुबंध अपने पास रखें, किसी और के पास नहीं।",
                "सहायता नंबर अपने फ़ोन में सेव कर लें।",
            ],
        ),
        (
            "अपना पैसा व्यवस्थित करें",
            [
                "देखें कि आपके पास ऐसा खाता है जिसमें नियोक्ता वेतन डाल सके।",
                "हर खर्च लिख लें, छोटा भी।",
            ],
        ),
        (
            "अपना अनुबंध समझें",
            [
                "अपना अनुबंध किसी भरोसेमंद व्यक्ति के साथ फिर से पढ़ें।",
                "अपना वेतन का दिन और वेतन से कटने वाली रकम लिख लें।",
            ],
        ),
        (
            "आपका पहला वेतन",
            ["देखें कि वेतन आपके अनुबंध से मेल खाता है।", "वेतन पर्ची संभालकर रखें।"],
        ),
        ("घर पैसे भेजें", ["भेजने से पहले सेवाओं की तुलना करें।", "तय रकम भेजें और रसीद रखें।"]),
        (
            "अपना खर्च जाँचें",
            ["जो खर्च हुआ उसे योजना से मिलाएँ।", "पैसे कम पड़ें तो कोई एक खर्च घटाएँ।"],
        ),
        (
            "लक्ष्यों पर टिके रहें",
            [
                "योजना के अनुसार हर लक्ष्य के लिए रकम अलग रखें।",
                "एक महीना मुश्किल लगे तो भी कोई लक्ष्य न छोड़ें।",
            ],
        ),
        (
            "आपात बचत बनाएँ",
            [
                "आपात स्थिति के लिए योजना में तय रकम अलग रखें।",
                "उसे ऐसी जगह रखें जहाँ से जल्दी निकाल सकें।",
            ],
        ),
        (
            "फिर घर पैसे भेजें",
            ["सेवाओं की फिर तुलना करें, क्योंकि दाम बदलते रहते हैं।", "हर रसीद रखें।"],
        ),
        (
            "अपने कागज़ात जाँचें",
            [
                "अपने दस्तावेज़ों की प्रतियाँ बनाकर सुरक्षित रखें।",
                "देखें कि आपका परमिट और पासपोर्ट कब खत्म होते हैं।",
            ],
        ),
        (
            "किसी भरोसेमंद से बात करें",
            [
                "वेतन या काम वादे के अनुसार न हो तो जल्दी किसी मज़दूर सहायता संगठन से बात करें।",
                "समस्या बड़ी होने तक इंतज़ार न करें।",
            ],
        ),
        (
            "अगले महीने की योजना",
            ["असल में जो खर्च हुआ उसके हिसाब से योजना बदलें।", "तय करें कि आप क्या बदलेंगे।"],
        ),
        (
            "पीछे मुड़कर देखें",
            [
                "तय रकम घर भेजें और रसीद रखें।",
                "इन तीन महीनों को पीछे मुड़कर देखें: क्या काम आया और क्या नहीं।",
            ],
        ),
    ],
    "tl": [
        (
            "Dumating at mag-ayos",
            [
                "Itago ang passport at kontrata mo; huwag ipaiwan sa iba.",
                "I-save ang mga helpline number sa phone mo.",
            ],
        ),
        (
            "Ayusin ang pera mo",
            [
                "Tiyaking may account ka na mapagpapasahan ng sahod ng employer.",
                "Isulat ang bawat gastos, kahit maliit.",
            ],
        ),
        (
            "Unawain ang kontrata",
            [
                "Basahin muli ang kontrata kasama ang taong pinagkakatiwalaan mo.",
                "Itala ang araw ng sahod at kung ano ang kinakaltas sa sahod mo.",
            ],
        ),
        ("Ang unang sahod mo", ["Tiyaking tugma ang sahod sa kontrata mo.", "Itago ang payslip."]),
        (
            "Magpadala ng pera",
            [
                "Ihambing ang mga serbisyo bago magpadala.",
                "Ipadala ang planadong halaga at itago ang resibo.",
            ],
        ),
        (
            "Suriin ang gastos",
            ["Ihambing ang ginastos mo sa plano.", "Magbawas ng isang gastos kung kapos ang pera."],
        ),
        (
            "Manatili sa mga layunin",
            [
                "Ilaan ang halagang nasa plano para sa bawat layunin.",
                "Huwag laktawan ang layunin dahil mahirap ang isang buwan.",
            ],
        ),
        (
            "Buuin ang pang-emergency",
            [
                "Ilaan ang halagang itinakda ng plano para sa emergency.",
                "Itago ito kung saan madali mong makukuha.",
            ],
        ),
        (
            "Magpadala muli",
            [
                "Ihambing muli ang mga serbisyo, dahil nagbabago ang presyo.",
                "Itago ang bawat resibo.",
            ],
        ),
        (
            "Suriin ang mga papeles",
            [
                "Gumawa ng kopya ng mga dokumento mo at itago nang ligtas.",
                "Alamin kung kailan mag-e-expire ang permit at passport mo.",
            ],
        ),
        (
            "Makipag-usap sa mapagkakatiwalaan",
            [
                "Kung hindi ayon sa pangako ang sahod o trabaho, makipag-usap nang maaga sa samahang tumutulong sa manggagawa.",
                "Huwag hintayin na lumaki ang problema.",
            ],
        ),
        (
            "Planuhin ang susunod na buwan",
            [
                "I-update ang plano batay sa totoong ginastos mo.",
                "Magpasya kung ano ang babaguhin mo.",
            ],
        ),
        (
            "Balikan ang nakaraan",
            [
                "Ipadala ang planadong halaga at itago ang resibo.",
                "Balikan ang tatlong buwang ito: ano ang gumana at ano ang hindi.",
            ],
        ),
    ],
}

CHECKLIST: dict[str, dict[str, str]] = {
    "en": {
        "keep_documents": "Keep copies of your contract, passport and agent receipts together.",
        "open_pay_account": "Open a bank account that your employer can pay into.",
        "keep_agent_receipts": "Keep every receipt for fees you paid to the recruitment agent.",
        "pay_costly_debt_first": "Pay the costly debt before saving more.",
        "compare_transfer_providers": "Compare ways to send money home before each transfer.",
        "save_helpline_numbers": "Save the numbers of a worker support group and your embassy.",
        "track_spending": "Write down your spending for the first month.",
    },
    "hi": {
        "keep_documents": "अपने अनुबंध, पासपोर्ट और एजेंट की रसीदों की प्रतियाँ एक साथ रखें।",
        "open_pay_account": "ऐसा बैंक खाता खोलें जिसमें आपका नियोक्ता वेतन डाल सके।",
        "keep_agent_receipts": "भर्ती एजेंट को दी गई फीस की हर रसीद रखें।",
        "pay_costly_debt_first": "ज़्यादा बचत करने से पहले महँगा कर्ज़ चुकाएँ।",
        "compare_transfer_providers": "हर बार पैसे भेजने से पहले तरीकों की तुलना करें।",
        "save_helpline_numbers": "किसी मज़दूर सहायता संगठन और अपने दूतावास के नंबर सेव करें।",
        "track_spending": "पहले महीने का अपना खर्च लिखें।",
    },
    "tl": {
        "keep_documents": "Itago nang magkakasama ang kopya ng kontrata, passport at resibo ng ahente.",
        "open_pay_account": "Magbukas ng bank account na mapagpapasahan ng sahod ng employer mo.",
        "keep_agent_receipts": "Itago ang bawat resibo ng bayad sa recruitment agent.",
        "pay_costly_debt_first": "Bayaran muna ang mahal na utang bago mag-ipon pa.",
        "compare_transfer_providers": "Ihambing ang mga paraan ng pagpapadala ng pera bago ang bawat padala.",
        "save_helpline_numbers": "I-save ang numero ng samahang tumutulong sa manggagawa at ng embahada mo.",
        "track_spending": "Isulat ang gastos mo sa unang buwan.",
    },
}

# Sentences with figures. `{c}` is the currency code; every figure is written as `1,234 CODE`.
WARNING: dict[str, dict[str, str]] = {
    "en": {
        "fee_above_legal_limit": "You paid {fee_paid} to the agent. The usual limit here is {usual_limit}. Keep your receipts and ask a worker support group to check it.",
        "high_interest_debt": "Your debt costs {rate}% each month. That is a lot. Pay it before you save more.",
        "debt_not_covered": "Your payment of {monthly_payment} does not cover the interest, so the debt will not end. Ask a worker support group for help.",
        "budget_shortfall": "Your costs and plans are {gap} more than your pay each month. Talk to a worker support group before you decide what to change.",
        "thin_emergency_fund": "You have {savings} saved and the emergency target is {target}. Saving a little each month will close the gap.",
        "no_pay_account": "You have no account to be paid into. Open one in your first week.",
        "no_provider_quote": "We cannot compare prices for sending money from here yet. Compare two or three services before you send.",
    },
    "hi": {
        "fee_above_legal_limit": "आपने एजेंट को {fee_paid} दिए। यहाँ आम सीमा {usual_limit} है। अपनी रसीदें रखें और किसी मज़दूर सहायता संगठन से जँचवाएँ।",
        "high_interest_debt": "आपके कर्ज़ पर हर महीने {rate}% ब्याज लगता है। यह बहुत है। ज़्यादा बचत करने से पहले इसे चुकाएँ।",
        "debt_not_covered": "आपकी {monthly_payment} की किस्त ब्याज भी नहीं भरती, इसलिए कर्ज़ खत्म नहीं होगा। किसी मज़दूर सहायता संगठन से मदद लें।",
        "budget_shortfall": "आपके खर्च और योजनाएँ हर महीने आपके वेतन से {gap} ज़्यादा हैं। क्या बदलना है, यह तय करने से पहले किसी मज़दूर सहायता संगठन से बात करें।",
        "thin_emergency_fund": "आपके पास {savings} की बचत है और आपात लक्ष्य {target} है। हर महीने थोड़ी बचत से यह फ़ासला भर जाएगा।",
        "no_pay_account": "आपके पास वेतन पाने के लिए कोई खाता नहीं है। पहले हफ़्ते में एक खोल लें।",
        "no_provider_quote": "हम अभी यहाँ से पैसे भेजने के दामों की तुलना नहीं कर सकते। भेजने से पहले दो-तीन सेवाओं की तुलना करें।",
    },
    "tl": {
        "fee_above_legal_limit": "Nagbayad ka ng {fee_paid} sa ahente. Ang karaniwang limitasyon dito ay {usual_limit}. Itago ang mga resibo at ipasuri sa samahang tumutulong sa manggagawa.",
        "high_interest_debt": "Ang utang mo ay may tubong {rate}% bawat buwan. Malaki iyon. Bayaran ito bago mag-ipon pa.",
        "debt_not_covered": "Ang bayad mong {monthly_payment} ay hindi sapat para sa tubo, kaya hindi matatapos ang utang. Humingi ng tulong sa samahang tumutulong sa manggagawa.",
        "budget_shortfall": "Ang mga gastos at plano mo ay lampas ng {gap} sa sahod mo bawat buwan. Makipag-usap sa samahang tumutulong sa manggagawa bago magpasya kung ano ang babaguhin.",
        "thin_emergency_fund": "May ipon kang {savings} at ang target para sa emergency ay {target}. Ang kaunting ipon bawat buwan ang pupuno sa kulang.",
        "no_pay_account": "Wala kang account na mapagpapasahan ng sahod. Magbukas ng isa sa unang linggo.",
        "no_provider_quote": "Hindi pa namin maihahambing ang presyo ng pagpapadala mula rito. Ihambing ang dalawa o tatlong serbisyo bago magpadala.",
    },
}


def _money(value: float, currency: str) -> str:
    return f"{round(value):,} {currency}"


def _summary(lang: str, facts: dict[str, Any]) -> str:
    cur = facts["currency"]
    income = _money(facts["monthly_budget"]["income"], cur)
    remit = _money(facts["remittance"]["monthly_amount"], cur)
    provider = facts["remittance"]["cheapest_provider"]
    debt = facts["debt"]
    fund = facts["emergency_fund"]
    months = None if debt is None else debt["months_to_clear"]
    target = _money(fund["target"], cur)
    weeks = fund["weeks_to_target"]
    if provider is None:
        send = {
            "en": f"After your costs, you plan to send {remit} home each month.",
            "hi": f"खर्चों के बाद आप हर महीने {remit} घर भेजने की योजना बना रहे हैं।",
            "tl": f"Pagkatapos ng mga gastos, plano mong magpadala ng {remit} sa pamilya bawat buwan.",
        }[lang]
    else:
        gets = _money(provider["family_receives"], provider["family_receives_currency"])
        send = {
            "en": f"After your costs, you can send {remit} home each month. {provider['name']} is the cheapest service we found and your family would receive {gets}.",
            "hi": f"खर्चों के बाद आप हर महीने {remit} घर भेज सकते हैं। {provider['name']} हमें मिली सबसे सस्ती सेवा है और आपके परिवार को {gets} मिलेंगे।",
            "tl": f"Pagkatapos ng mga gastos, makapagpapadala ka ng {remit} sa pamilya bawat buwan. Ang {provider['name']} ang pinakamurang serbisyong nakita namin at tatanggap ang pamilya mo ng {gets}.",
        }[lang]
    parts = [
        {
            "en": f"You will earn about {income} a month.",
            "hi": f"आप महीने में लगभग {income} कमाएँगे।",
            "tl": f"Kikita ka ng humigit-kumulang {income} bawat buwan.",
        }[lang],
        send,
    ]
    if months is not None:
        parts.append(
            {
                "en": f"Your debt can be paid off in about {months} months.",
                "hi": f"आपका कर्ज़ लगभग {months} महीनों में चुकाया जा सकता है।",
                "tl": f"Ang utang mo ay mababayaran sa humigit-kumulang {months} buwan.",
            }[lang]
        )
    if weeks:
        parts.append(
            {
                "en": f"An emergency fund of {target} needs about {weeks} weeks of saving.",
                "hi": f"{target} का आपात कोष बनाने में लगभग {weeks} हफ़्ते की बचत लगेगी।",
                "tl": f"Ang pang-emergency na {target} ay aabutin ng humigit-kumulang {weeks} linggo ng pag-iipon.",
            }[lang]
        )
    return " ".join(parts)


def _warning_text(lang: str, spec_id: str, about: dict[str, Any], currency: str) -> str:
    money = {
        key: _money(value, currency)
        for key, value in about.items()
        if key in {"fee_paid", "usual_limit", "monthly_payment", "gap", "savings", "target"}
    }
    rate = about.get("interest_percent_per_month")
    fields: dict[str, Any] = {**money, "rate": f"{rate:g}" if rate is not None else ""}
    return WARNING[lang][spec_id].format(**fields)


def plan_text(
    lang: str, facts: dict[str, Any], warnings: list[tuple[str, dict[str, Any]]], items: list[str]
) -> PlanText:
    """The plan's sentences in `lang`, around the facts the plan was built from."""
    cur = facts["currency"]
    return PlanText(
        summary=_summary(lang, facts),
        weeks=[
            WeekText(week=n, title=title, actions=actions)
            for n, (title, actions) in enumerate(WEEKS[lang], start=1)
        ],
        warnings=[
            NoteText(id=spec_id, text=_warning_text(lang, spec_id, about, cur))
            for spec_id, about in warnings
        ],
        checklist=[NoteText(id=item, text=CHECKLIST[lang][item]) for item in items],
    )


def translation(
    lang: str, facts: dict[str, Any], warnings: list[tuple[str, dict[str, Any]]], items: list[str]
) -> PlanTranslation:
    """The same narrative as `plan_text`, in the shape the translator step returns."""
    text = plan_text(lang, facts, warnings, items)
    return PlanTranslation(
        summary=text.summary,
        weeks=text.weeks,
        warnings=text.warnings,
        checklist=text.checklist,
        disclaimer=NOT_ADVICE_NOTE[lang],  # type: ignore[index]
    )
