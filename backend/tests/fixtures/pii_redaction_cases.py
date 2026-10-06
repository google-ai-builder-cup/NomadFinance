"""NF-F0-008: 60 synthetic messages with the personal values that must not survive redaction.

Every number, address and handle here is made up. Each case is (text, values): `values` are the
exact substrings of `text` that identify someone, and the redactor must remove all of them.
Cases are grouped by corridor country, then by message language.
"""

from __future__ import annotations

PII_CASES: list[tuple[str, tuple[str, ...]]] = [
    # --- Singapore (SG->PH, SG->IN) ---
    (
        "Hi, this is Mr Tan from the agency. Call me on +65 9123 4567 about your work pass.",
        ("+65 9123 4567",),
    ),
    ("WhatsApp 91234567 now to confirm your slot.", ("91234567",)),
    (
        "Reply to jobs.sg.agency@gmail.com with your NRIC S1234567D.",
        ("jobs.sg.agency@gmail.com", "S1234567D"),
    ),
    ("Your FIN is G7654321K, keep it safe. Hotline 6123-4567.", ("G7654321K", "6123-4567")),
    ("Transfer the fee to DBS 012-345-678-9 before Friday.", ("012-345-678-9",)),
    (
        "Pay at https://sg-workpass-fee.top/pay?id=88123 within 24 hours.",
        ("https://sg-workpass-fee.top/pay?id=88123",),
    ),
    (
        "Add me on wa.me/6591234567 and send your passport K1234567A.",
        ("wa.me/6591234567", "K1234567A"),
    ),
    ("OCBC a/c no. 501234567890, name on the account must match.", ("501234567890",)),
    ("Contact (+65) 8123 4567 or +65-6234-5678 after 6pm.", ("(+65) 8123 4567", "+65-6234-5678")),
    ("Visit www.mom-verify.com/login to keep your pass active.", ("www.mom-verify.com/login",)),
    # --- Philippines (SG->PH, JP->PH, AU->PH) ---
    ("Text me at 0917 123 4567 for the GCash number.", ("0917 123 4567",)),
    ("Send the placement fee to 09171234567 via GCash.", ("09171234567",)),
    (
        "Call +63 917 123 4567 or +63-2-8123-4567 for the POEA slot.",
        ("+63 917 123 4567", "+63-2-8123-4567"),
    ),
    ("My passport is P1234567A and my UMID is 0012-3456789-0.", ("P1234567A", "0012-3456789-0")),
    ("SSS number 33-1234567-8 is needed for the contribution.", ("33-1234567-8",)),
    (
        "PhilSys ID 1234-5678-9012 attached, email maria.santos@yahoo.com.ph.",
        ("1234-5678-9012", "maria.santos@yahoo.com.ph"),
    ),
    (
        "BDO account number 001234567890, send the proof to this number 0928 765 4321.",
        ("001234567890", "0928 765 4321"),
    ),
    ("Bisitahin ang bit.ly/ofw-loan-2026 para sa mabilis na loan.", ("bit.ly/ofw-loan-2026",)),
    (
        "Padala mo sa account 1234 5678 9012, tawagan ako sa +63 998 765 4321.",
        ("1234 5678 9012", "+63 998 765 4321"),
    ),
    ("Kailangan ko ang passport mo: EC1234567 at TIN 123-456-789.", ("EC1234567", "123-456-789")),
    # --- India (SG->IN, AU->IN) ---
    ("Call 98765 43210 now, your job is confirmed.", ("98765 43210",)),
    (
        "WhatsApp +91 98765 43210 or mail hr.recruit2026@outlook.com.",
        ("+91 98765 43210", "hr.recruit2026@outlook.com"),
    ),
    (
        "Aadhaar 2345 6789 0123 and PAN ABCDE1234F are required for KYC.",
        ("2345 6789 0123", "ABCDE1234F"),
    ),
    ("Pay to UPI id rahul.kumar@okaxis to book the visa slot.", ("rahul.kumar@okaxis",)),
    ("SBI account number 12345678901 IFSC SBIN0001234, send the fee today.", ("12345678901",)),
    ("Indian passport J8369854 expires next year.", ("J8369854",)),
    (
        "Your voter ID XYZ1234567 is linked, click http://kyc-update-india.in/verify now.",
        ("XYZ1234567", "http://kyc-update-india.in/verify"),
    ),
    ("Send to rakesh@paytm and confirm on 99887 76655.", ("rakesh@paytm", "99887 76655")),
    # --- Indonesia / Malaysia (MY->ID) ---
    ("Hubungi 0812-3456-7890 untuk info lowongan di Malaysia.", ("0812-3456-7890",)),
    (
        "Transfer ke rekening BCA 1234567890 a.n. PT Maju, konfirmasi ke +62 812 3456 7890.",
        ("1234567890", "+62 812 3456 7890"),
    ),
    ("NIK saya 3174012345670001, paspor B1234567.", ("3174012345670001", "B1234567")),
    (
        "Klik https://tki-malaysia.xyz/daftar untuk daftar sekarang.",
        ("https://tki-malaysia.xyz/daftar",),
    ),
    (
        "Kirim CV ke rekrut.tki@gmail.com atau WA 0857 1234 5678.",
        ("rekrut.tki@gmail.com", "0857 1234 5678"),
    ),
    (
        "Call 012-345 6789 or 011-2345 6789 for the Kuala Lumpur job.",
        ("012-345 6789", "011-2345 6789"),
    ),
    ("Malaysian IC 900101-14-5678, passport A12345678.", ("900101-14-5678", "A12345678")),
    ("Maybank account 5123 4567 8901 please pay the levy.", ("5123 4567 8901",)),
    (
        "Email: majikan.sdn.bhd@gmail.com, tel +60 12-345 6789.",
        ("majikan.sdn.bhd@gmail.com", "+60 12-345 6789"),
    ),
    (
        "Nomor rekening: 0123456789, atas nama Budi, kirim bukti ke t.me/agen_tki_resmi.",
        ("0123456789", "t.me/agen_tki_resmi"),
    ),
    # --- Japan (JP->PH) ---
    ("Call 090-1234-5678 for the technical intern job.", ("090-1234-5678",)),
    ("Residence card number AB12345678CD is on the front.", ("AB12345678CD",)),
    ("My passport TR1234567 and phone +81 90 1234 5678.", ("TR1234567", "+81 90 1234 5678")),
    (
        "Tokyo office 03-1234-5678, mail recruit@nihon-jobs.co.jp.",
        ("03-1234-5678", "recruit@nihon-jobs.co.jp"),
    ),
    ("Bank transfer to Mizuho account 1234567 branch 123 is not safe.", ("1234567",)),
    # --- Australia (AU->IN, AU->PH) ---
    ("Text 0412 345 678 about the farm work visa.", ("0412 345 678",)),
    ("Call +61 412 345 678 or (02) 9123 4567.", ("+61 412 345 678", "(02) 9123 4567")),
    ("Passport N1234567 and TFN 123 456 782 are needed.", ("N1234567", "123 456 782")),
    ("Pay the sponsor fee to BSB 062-000 account 12345678 now.", ("12345678",)),
    (
        "Check https://aus-visa-grant.link/status for your grant.",
        ("https://aus-visa-grant.link/status",),
    ),
    # --- Hindi, Nepali, Bengali (native digits and mixed text) ---
    ("मुझे ९८७६५ ४३२१० पर फोन करें।", ("९८७६५ ४३२१०",)),
    ("मेरा खाता संख्या १२३४५६७८९०१२ है।", ("१२३४५६७८९०१२",)),
    (
        "मेरा ईमेल sunita.devi@gmail.com है और पासपोर्ट J8369854।",
        ("sunita.devi@gmail.com", "J8369854"),
    ),
    ("मलाई ९८४१२३४५६७ मा फोन गर्नुहोस्।", ("९८४१२३४५६७",)),
    ("आफ्नो राहदानी नम्बर PA1234567 पठाउनुहोस्।", ("PA1234567",)),
    (
        "আমার নম্বর ০১৭১২৩৪৫৬৭৮, ইমেইল rahim.uddin@gmail.com।",
        ("০১৭১২৩৪৫৬৭৮", "rahim.uddin@gmail.com"),
    ),
    ("আমার একাউন্ট নম্বর ১২৩৪৫৬৭৮৯০১২৩ এ টাকা পাঠান।", ("১২৩৪৫৬৭৮৯০১২৩",)),
    # --- Obfuscation and mixed content ---
    ("Mail me at agent [at] gmail [dot] com and I will reply.", ("agent [at] gmail [dot] com",)),
    ("Open hxxps://free-visa[.]top/claim to claim.", ("hxxps://free-visa[.]top/claim",)),
    ("Account no. 4111 1111 1111 1111, CVV is not needed.", ("4111 1111 1111 1111",)),
    (
        "Send 500 SGD to account 123-456-789 and WhatsApp 8123 4567 with the receipt.",
        ("123-456-789", "8123 4567"),
    ),
    (
        "Congratulations! Pay 2000 as fee to 9876543210123 today, call +91 99887 76655, "
        "mail win@lucky-draw.biz.",
        ("9876543210123", "+91 99887 76655", "win@lucky-draw.biz"),
    ),
]

# Text with nothing personal in it. Amounts, dates, times and percentages are the main risk:
# masking them would hide the evidence the scam analyser and the coach need.
CLEAN_CASES: list[str] = [
    "You have been selected for a caregiver job in Singapore, salary SGD 1,200.50 a month.",
    "Pay Rp 5.000.000 as the agency fee before 2026-10-06 at 13:45.",
    "The recruiter wants Rs 5,00,000 and says the visa is guaranteed in 7 days.",
    "Send 500 USD within 24 hours or the slot is cancelled.",
    "My salary is 2500 per month and I owe 12000 on a loan at 18% interest.",
    "The contract is for 24 months, 48 hours a week, with 1 day off.",
    "Meet at the office on 12 06 2026, bring 2 photos.",
    "Sir.My name is Ramesh and I work in Dubai... no, in Doha.",
    "I send PHP 15 000 home every month, about 3% of it is lost in fees.",
    "Exchange rate today is 1 SGD = 62.35 PHP, version 2.1 of the app.",
    "Overtime is 1.5 times the hourly rate of 4.50 dollars.",
    "This is not a scam, please read the notice carefully.",
    "मेरी तनख्वाह ५००० रुपये है और मुझे १२ घंटे काम करना पड़ता है।",
    "আমার বেতন ২৫০০ টাকা, ৮ ঘণ্টা কাজ।",
    "Ang sahod ko ay 1500 piso kada linggo.",
]
