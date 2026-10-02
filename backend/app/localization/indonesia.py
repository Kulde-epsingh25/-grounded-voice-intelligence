"""Indonesia market localization configuration (Multifinance / Consumer Finance domain)."""
from __future__ import annotations

from app.localization.models import (
    Language,
    LocalizationExample,
    LocalizedPhrasingSet,
    Market,
    MarketConfig,
    Register,
    Sector,
)
from app.localization.terminology import ID_TERMINOLOGY_LIST

ID_LOCALIZATION_EXAMPLES: list[LocalizationExample] = [
    LocalizationExample(
        category="greeting",
        english_intent="Hello, welcome to our loan department. How can I help you?",
        localized_wording="Selamat pagi Bapak/Ibu, terima kasih telah menghubungi layanan pembiayaan kami. Ada yang bisa kami bantu terkait simulasi cicilan atau pengajuan dana multiguna hari ini?",
        why_localized="Literal translation sounds robotic and ignores Indonesian business etiquette. Formal greeting with 'Bapak/Ibu' and industry-standard terms 'pembiayaan' and 'cicilan' conveys regulatory legitimacy and respect.",
        cultural_consideration="Indonesian corporate financial customer service demands respectful honorifics ('Bapak' for male, 'Ibu' for female, or 'Kakak/Kak' in digital retail consumer apps).",
        market=Market.ID,
        language=Language.ID_FORMAL,
        conversational_register=Register.FORMAL,
    ),
    LocalizationExample(
        category="objection_interest_rate",
        english_intent="Our interest rate is reasonable and complies with regulations.",
        localized_wording="Bisa kami pahami pertimbangan Bapak/Ibu. Perlu kami sampaikan bahwa besaran suku bunga dan biaya pembiayaan kami sudah sepenuhnya transparan serta mengikuti regulasi OJK, tanpa ada biaya tersembunyi saat jatuh tempo.",
        why_localized="Directly arguing about interest rates triggers distrust regarding predatory lending (pinjol ilegal). Explicitly citing transparency and OJK (Otoritas Jasa Keuangan) compliance reassures the applicant about safety and fair installment ('cicilan').",
        cultural_consideration="Consumers in Indonesia are highly cautious of predatory illegal lenders; referencing compliance and absence of hidden penalty fees ('tanpa denda tersembunyi') is critical for trust.",
        market=Market.ID,
        language=Language.ID_FORMAL,
        conversational_register=Register.FORMAL,
    ),
    LocalizationExample(
        category="clarification_down_payment",
        english_intent="How much initial money down will you provide?",
        localized_wording="Boleh tahu Kak, untuk DP atau uang muka yang disiapkan kira-kira di kisaran berapa persen atau berapa juta?",
        why_localized="In conversational consumer finance, using the loanword 'DP' (/de-pe/) and friendly address 'Kak' feels natural and modern, avoiding stiff textbook Indonesian ('uang panjar awal').",
        cultural_consideration="Modern urban Indonesian retail finance widely uses 'DP' and 'tenor' as natural conversational loanwords.",
        market=Market.ID,
        language=Language.ID_COLLOQUIAL,
        conversational_register=Register.COLLOQUIAL,
    ),
    LocalizationExample(
        category="human_escalation",
        english_intent="Transferring you to an agent.",
        localized_wording="Baik Kak, biar lebih jelas dan bisa dibantu hitungkan simulasi cicilannya secara detail, langsung aku sambungkan ke representatif pembiayaan kami ya. Mohon tunggu sebentar.",
        why_localized="Colloquial warmth ('langsung aku sambungkan ya') makes the transfer feel like helpful customer advocacy rather than an automated deflection.",
        cultural_consideration="Promotes relational warmth (kekeluargaan) and helpful personal service.",
        market=Market.ID,
        language=Language.ID_COLLOQUIAL,
        conversational_register=Register.COLLOQUIAL,
    ),
]

# Formal Register Phrasings (B2B, Official Multifinance)
ID_FORMAL_PHRASINGS = LocalizedPhrasingSet(
    greeting=[
        "Selamat pagi Bapak/Ibu, terima kasih telah menghubungi layanan pembiayaan kami. Ada yang bisa kami bantu terkait pengajuan fasilitas dana atau simulasi angsuran hari ini?",
        "Halo, selamat datang di layanan konsultasi pembiayaan konsumen. Apakah berkenan kami bantu untuk verifikasi kelayakan kredit Anda?",
    ],
    permission_request=[
        "Apakah Bapak/Ibu bersedia untuk menjawab beberapa pertanyaan singkat guna memproses simulasi pembiayaan ini?",
        "Mohon izin untuk mencatat rincian kebutuhan kredit Bapak/Ibu demi kelancaran proses verifikasi.",
    ],
    qualification_prompts={
        "business_type": "Boleh diinformasikan jenis pekerjaan atau bidang usaha yang sedang Bapak/Ibu jalankan saat ini?",
        "years_in_business": "Sudah berapa lama bidang usaha atau masa kerja Bapak/Ibu berjalan?",
        "monthly_revenue": "Berapa rata-rata penghasilan kotor atau omzet bulanan yang diperoleh setiap bulannya?",
        "requested_amount": "Berapa estimasi nominal pembiayaan yang ingin Bapak/Ibu ajukan?",
        "loan_purpose": "Untuk tujuan apa fasilitas pembiayaan ini akan digunakan—apakah modal kerja, pembelian kendaraan, atau renovasi?",
        "contact_permission": "Apakah Bapak/Ibu menyetujui jika staf konsultan pembiayaan kami menghubungi kembali untuk menyampaikan rincian jadwal cicilan?",
    },
    objection_responses={
        "too_expensive": "Dapat kami pahami kekhawatiran Bapak/Ibu. Kami menyediakan berbagai pilihan tenor hingga 60 bulan agar cicilan bulanan tetap terjangkau dan sesuai anggaran.",
        "penalty_too_high": "Mengenai denda keterlambatan, hal ini hanya berlaku jika pembayaran melewati batas jatuh tempo. Kami juga menyediakan fasilitas auto-debet perbankan agar terhindar dari denda.",
        "need_to_think": "Baik Bapak/Ibu, keputusan finansial tentu memerlukan pertimbangan matang. Kami dapat mengirimkan lembar simulasi resmi ke email atau WhatsApp Bapak/Ibu terlebih dahulu.",
    },
    clarification=[
        "Mohon maaf, bisakah Bapak/Ibu memperjelas nominal yang dimaksud dalam rupiah?",
        "Apakah yang Bapak/Ibu maksud adalah lima puluh juta atau lima ratus juta rupiah?",
    ],
    fallback=[
        "Mohon maaf Bapak/Ibu, kami belum memiliki informasi resmi mengenai hal tersebut pada basis data kami. Apakah berkenan saya sambungkan dengan staf layanan pembiayaan kami?",
    ],
    escalation=[
        "Baik Bapak/Ibu, saya akan segera menyambungkan panggilan ini ke staf customer service kami. Mohon ditunggu sejenak.",
    ],
    closing=[
        "Terima kasih atas waktu dan kepercayaan Bapak/Ibu. Semoga hari Anda menyenangkan dan salam sukses selalu.",
    ],
)

# Colloquial Register Phrasings (Retail consumer finance, auto-loan apps)
ID_COLLOQUIAL_PHRASINGS = LocalizedPhrasingSet(
    greeting=[
        "Halo Kak! Selamat datang di layanan pembiayaan cepat kami. Mau dibantu cek simulasi cicilan atau pengajuan dana apa nih hari ini?",
        "Hai Kak! Mau info soal kredit motor, mobil, atau dana multiguna? Yuk, aku bantu hitung cicilannya.",
    ],
    permission_request=[
        "Boleh ya Kak, aku tanya-tanya sedikit buat cek estimasi cicilan yang paling pas buat budget Kakak?",
        "Kita mulai cek datanya ya Kak, cuma butuh waktu sebentar kok.",
    ],
    qualification_prompts={
        "business_type": "Saat ini lagi usaha di bidang apa atau kerja sebagai apa nih Kak?",
        "years_in_business": "Udah berapa lama nih usahanya atau kerja di tempat yang sekarang?",
        "monthly_revenue": "Kira-kira rata-rata pemasukan atau gaji per bulan berapa ya Kak?",
        "requested_amount": "Rencana mau ngajuin pinjaman berapa juta nih Kak?",
        "loan_purpose": "Dananya rencana mau dipake buat apa nih Kak—modal usaha, beli kendaraan, atau kebutuhan lain?",
        "contact_permission": "Boleh ya Kak kalau nanti tim staf kami hubungi via WhatsApp atau telepon buat kasih rincian cicilannya?",
    },
    objection_responses={
        "too_expensive": "Tenang Kak, kita bisa atur tenor lebih panjang kok biar cicilan per bulannya lebih ringan dan nggak bikin pusing.",
        "penalty_too_high": "Soal denda, asal bayar sebelum tanggal jatuh tempo aman banget kok Kak, nggak bakal kena denda sama sekali.",
        "need_to_think": "Iya nggak masalah Kak, santai aja. Mau aku kirimin ringkasan simulasi cicilannya dulu ke WhatsApp?",
    },
    clarification=[
        "Boleh diperjelas lagi nggak Kak nominalnya, maksudnya lima puluh juta apa lima juta rupiah?",
        "Kira-kira jumlah pastinya berapa rupiah ya Kak?",
    ],
    fallback=[
        "Waduh mohon maaf Kak, info soal itu belum ada di panduan resmi kami nih. Mau aku hubungkan langsung sama customer service kami biar dibantu?",
    ],
    escalation=[
        "Siap Kak, langsung aku sambungkan ke tim representatif kami ya. Ditunggu sebentar ya Kak.",
    ],
    closing=[
        "Makasih banyak ya Kak udah ngobrol bareng. Semoga lancar terus usahanya!",
    ],
)

ID_MARKET_CONFIG = MarketConfig(
    market=Market.ID,
    sector=Sector.MULTIFINANCE,
    supported_languages=[Language.ID_FORMAL, Language.ID_COLLOQUIAL, Language.ID_MIXED],
    default_language=Language.ID_FORMAL,
    default_register=Register.FORMAL,
    transcriber_config={
        "provider": "deepgram",
        "model": "nova-3",
        "language": "multi",
        "smart_format": True,
        "keywords": [
            "cicilan:2.0",
            "tenor:2.0",
            "denda:2.0",
            "DP:2.0",
            "jatuh tempo:2.0",
            "angsuran:2.0",
            "pembiayaan:2.0",
            "multifinance:1.5",
            "Bapak:1.0",
            "Ibu:1.0",
        ],
    },
    tts_config={
        "provider": "elevenlabs",
        "model": "eleven_multilingual_v2",
        "voice_id": "id_indonesian_female_01",
        "language": "id",
        "latency_target": 250,
    },
    greeting_style="respectful_formal_or_warm_colloquial",
    fallback_style="preserve_indonesian_register",
    escalation_style="connect_to_multifinance_specialist",
    terminology=ID_TERMINOLOGY_LIST,
    phrasings={
        Language.ID_FORMAL: ID_FORMAL_PHRASINGS,
        Language.ID_COLLOQUIAL: ID_COLLOQUIAL_PHRASINGS,
    },
    politeness_particles=["Bapak", "Ibu", "Kak", "mohon", "terima kasih", "silakan"],
)
