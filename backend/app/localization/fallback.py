"""Localized fallback policy maintaining language continuity and conversational register."""
from __future__ import annotations

from typing import Optional
from app.localization.models import (
    Language,
    Market,
    Register,
)

FALLBACK_MESSAGES: dict[tuple[Language, str], str] = {
    # Philippines - Taglish
    (Language.TAGLISH, "unsupported_kb"): (
        "Pasensya na po, wala po akong verified na impormasyon tungkol diyan sa aming official guidelines. "
        "Gusto niyo po bang ikonekta ko kayo sa ating Bancassurance Specialist?"
    ),
    (Language.TAGLISH, "unclear_audio"): (
        "Pasensya na po, medyo hindi ko po naintindihan nang malinaw. Pwede po bang pakiulit?"
    ),
    (Language.TAGLISH, "tool_failure"): (
        "Paumanhin po, nagkaroon po ng technical delay sa aming system. "
        "I-record ko po ang inyong inquiry para matawagan kayo ng aming team."
    ),
    (Language.TAGLISH, "human_escalation"): (
        "Opo, nauunawaan ko po. I-transfer ko na po kayo ngayon sa ating insurance financial specialist. Sandali lamang po."
    ),

    # Philippines - Pure Filipino / Tagalog
    (Language.FIL, "unsupported_kb"): (
        "Ipagpaumanhin po ninyo, wala po akong nahanap na opisyal na impormasyon ukol diyan sa ating gabay. "
        "Nais po ba ninyong makausap ang ating tagapayo sa bangko?"
    ),
    (Language.FIL, "unclear_audio"): (
        "Paumanhin po, hindi ko po gaanong narinig. Maaari po bang pakisabi muli?"
    ),
    (Language.FIL, "tool_failure"): (
        "Paumanhin po, may kaunting aberya sa sistema. Itatala ko po ito upang mabalikan kayo."
    ),
    (Language.FIL, "human_escalation"): (
        "Opo, agad ko po kayong ikokonekta sa isang kinatawan. Mangyaring maghintay po nang sandali."
    ),

    # Philippines - English
    (Language.EN, "unsupported_kb"): (
        "I don't have verified information about that in our bancassurance policies. "
        "Would you like me to connect you with an insurance specialist?"
    ),
    (Language.EN, "unclear_audio"): (
        "I'm sorry, I didn't quite catch that. Could you please repeat?"
    ),
    (Language.EN, "tool_failure"): (
        "I apologize, our system is currently experiencing a temporary delay. "
        "I'll note your inquiry for a callback from our underwriting team."
    ),
    (Language.EN, "human_escalation"): (
        "Certainly. I am transferring you to a lending specialist right now. Please hold on."
    ),

    # Indonesia - Formal Bahasa Indonesia
    (Language.ID_FORMAL, "unsupported_kb"): (
        "Mohon maaf Bapak/Ibu, kami belum memiliki informasi resmi mengenai hal tersebut pada basis data kami. "
        "Apakah berkenan saya sambungkan dengan staf layanan pembiayaan kami?"
    ),
    (Language.ID_FORMAL, "unclear_audio"): (
        "Mohon maaf, suara Bapak/Ibu kurang terdengar jelas. Apakah bisa diulangi kembali?"
    ),
    (Language.ID_FORMAL, "tool_failure"): (
        "Mohon maaf atas ketidaknyamanannya, sistem kami sedang mengalami kendala teknis. "
        "Data permohonan Anda telah kami catat untuk ditindaklanjuti oleh petugas kami."
    ),
    (Language.ID_FORMAL, "human_escalation"): (
        "Baik Bapak/Ibu, saya akan segera menyambungkan panggilan ini ke staf customer service kami. Mohon ditunggu sejenak."
    ),

    # Indonesia - Colloquial Bahasa Indonesia
    (Language.ID_COLLOQUIAL, "unsupported_kb"): (
        "Waduh mohon maaf Kak, info soal itu belum ada di panduan resmi kami nih. "
        "Mau aku hubungkan langsung sama customer service kami biar dibantu?"
    ),
    (Language.ID_COLLOQUIAL, "unclear_audio"): (
        "Maaf Kak, tadi suaranya agak putus-putus. Boleh diulang lagi nggak?"
    ),
    (Language.ID_COLLOQUIAL, "tool_failure"): (
        "Wah maaf banget Kak, sistemnya lagi agak lambat nih. "
        "Tenang aja, datanya udah aku simpan biar nanti dihubungi sama tim kami ya."
    ),
    (Language.ID_COLLOQUIAL, "human_escalation"): (
        "Siap Kak, langsung aku sambungkan ke tim representatif kami ya. Ditunggu sebentar ya Kak."
    ),

    # Indonesia - Mixed
    (Language.ID_MIXED, "unsupported_kb"): (
        "Mohon maaf, informasi terkait hal tersebut belum tersedia di sistem kami. "
        "Apakah ingin dihubungkan langsung dengan staf pembiayaan kami?"
    ),
    (Language.ID_MIXED, "unclear_audio"): (
        "Mohon maaf, suaranya kurang jelas. Bisa tolong diulangi kembali?"
    ),
    (Language.ID_MIXED, "tool_failure"): (
        "Mohon maaf, terjadi kendala pada sistem. Catatan Anda telah kami simpan untuk penanganan lebih lanjut."
    ),
    (Language.ID_MIXED, "human_escalation"): (
        "Baik, panggilan ini akan segera saya teruskan ke staf kami. Mohon ditunggu sebentar."
    ),
}


class LocalizedFallbackManager:
    """Provides culturally and linguistically appropriate fallback responses."""

    @classmethod
    def get_fallback(
        cls,
        market: Market,
        language: Language,
        reason: str = "unsupported_kb",
        register: Optional[Register] = None,
    ) -> str:
        """Retrieve fallback message preserving caller language and register."""
        # Exact match
        key = (language, reason)
        if key in FALLBACK_MESSAGES:
            return FALLBACK_MESSAGES[key]

        # Register-based fallback for ID
        if market == Market.ID:
            if register == Register.COLLOQUIAL:
                fallback_lang = Language.ID_COLLOQUIAL
            elif register == Register.FORMAL:
                fallback_lang = Language.ID_FORMAL
            else:
                fallback_lang = Language.ID_MIXED
            return FALLBACK_MESSAGES.get((fallback_lang, reason), FALLBACK_MESSAGES[(Language.ID_FORMAL, reason)])

        # Default for PH
        return FALLBACK_MESSAGES.get((Language.TAGLISH, reason), FALLBACK_MESSAGES[(Language.EN, reason)])
