"""Philippines market localization configuration (Life Insurance / Bancassurance domain)."""
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
from app.localization.terminology import PH_TERMINOLOGY_LIST

# Documented localization examples showing non-literal adaptation
PH_LOCALIZATION_EXAMPLES: list[LocalizationExample] = [
    LocalizationExample(
        category="greeting",
        english_intent="Hello! Thank you for calling the bank. How can I help you today?",
        localized_wording="Magandang araw po! Ako po ang inyong Bancassurance Virtual Assistant mula sa partner bank. Kumusta po, may maitutulong po ba ako sa inyong policy inquiry o life coverage ngayon?",
        why_localized="Direct word-for-word translation sounds robotic and unnatural. Taglish with respectful markers ('po', 'kumusta po') builds immediate warmth and trust (malasakit), while stating bank partnership clarifies legitimacy.",
        cultural_consideration="Filipino customer service strictly requires respectful honorifics ('po' / 'opo') even in digital voice bots. Bancassurance requires explicit reference to the partner bank to overcome insurance sales skepticism.",
        market=Market.PH,
        language=Language.TAGLISH,
        conversational_register=Register.FORMAL,
    ),
    LocalizationExample(
        category="objection_price",
        english_intent="The premium is not expensive when you consider the death benefit.",
        localized_wording="Naiintindihan ko po kayo. Pero kung titingnan po natin, para lang po itong bawas sa araw-araw na gastos para masiguradong may maaasahang pondo ang inyong pamilya kung sakaling magkaroon ng emergency.",
        why_localized="Directly arguing 'it is not expensive' violates Filipino conversational politeness (pakikipagkapwa). Framing premium as everyday small savings ('bawas sa araw-araw na gastos') aligns with the cultural concept of family security and mutual aid (damayan).",
        cultural_consideration="Avoids defensive financial jargon; focuses on peace of mind and family protection rather than clinical investment returns.",
        market=Market.PH,
        language=Language.TAGLISH,
        conversational_register=Register.MIXED,
    ),
    LocalizationExample(
        category="clarification_income",
        english_intent="State your exact monthly disposable income.",
        localized_wording="Para po ma-check natin ang pinaka-akmang plan para sa budget ninyo, mga magkano po ang komportable ninyong maitabi kada buwan?",
        why_localized="Directly demanding financial statements or disposable income causes embarrassment (hiya). Asking how much they can comfortably set aside ('komportableng maitabi kada buwan') is non-intrusive and respectful.",
        cultural_consideration="Respects financial modesty (hiya) and ensures the client feels empowered rather than audited during preliminary qualification.",
        market=Market.PH,
        language=Language.TAGLISH,
        conversational_register=Register.FORMAL,
    ),
    LocalizationExample(
        category="human_escalation",
        english_intent="I will transfer you to an agent.",
        localized_wording="Walang problema po. Ikokonekta ko po kayo agad sa ating licensed Bancassurance Financial Specialist para ma-assist po kayo nang mas detalyado. Pakiantay lang po sandali.",
        why_localized="Reassures the client that the transfer is warm, seamless, and handled by an authorized licensed specialist at the bank branch.",
        cultural_consideration="Filipino consumers place high value on speaking with certified professionals when discussing serious family wealth protection.",
        market=Market.PH,
        language=Language.TAGLISH,
        conversational_register=Register.FORMAL,
    ),
]

PH_TAGLISH_PHRASINGS = LocalizedPhrasingSet(
    greeting=[
        "Magandang araw po! Ako po ang inyong Bancassurance Virtual Assistant mula sa partner bank. Paano ko po kayo matutulungan ngayon?",
        "Hello po! Welcome sa ating bancassurance consultation service. Nais niyo po bang mag-inquire tungkol sa life coverage o savings plan?",
    ],
    permission_request=[
        "Okay lang po ba sa inyo kung magtanong ako ng ilang maikling detalye para ma-check natin ang tamang plan para sa inyo?",
        "Maaari po ba nating simulan ang inyong quick qualification check para sa policy protection?",
    ],
    qualification_prompts={
        "business_type": "Ano po ang kasalukuyang propesyon o source of livelihood ninyo ngayon?",
        "years_in_business": "Ilang taon na po kayong nagtatrabaho o nagpapatakbo ng inyong negosyo?",
        "monthly_revenue": "Mga magkano po ang average monthly income o kinikita ninyo kada buwan?",
        "requested_amount": "Magkano po ang target coverage o sum assured na gusto ninyong ma-secure para sa pamilya?",
        "loan_purpose": "Ano po ang pangunahing layunin ng plan—proteksyon po ba sa kalusugan, education fund, o retirement savings?",
        "contact_permission": "Pumapayag po ba kayo na tawagan kayo ng ating licensed Bancassurance Specialist sa branch para sa inyong personalized proposal?",
    },
    objection_responses={
        "too_expensive": "Nauunawaan ko po kayo. Mayroon po tayong flexible payment options tulad ng quarterly o monthly auto-debit para hindi mabigat sa bulsa.",
        "already_have_insurance": "Maganda po iyan na may existing coverage na kayo! Karaniwan po, nagdadagdag ang ating clients ng critical illness rider para mas buo ang proteksyon.",
        "need_to_think": "Opo, naiintindihan ko po na mahalagang desisyon ito para sa pamilya. Pwede ko po bang ipadala ang summary sa inyong email o mag-schedule ng branch visit?",
    },
    clarification=[
        "Maaari po bang pakilinaw kung magkano po ang eksaktong halaga na tinutukoy ninyo sa piso?",
        "Pasensya na po, ibig sabihin po ba ninyo ay limampung libo o limang daang libong piso?",
    ],
    fallback=[
        "Pasensya na po, wala po akong verified na impormasyon tungkol diyan sa aming official guidelines. Gusto niyo po bang ikonekta ko kayo sa ating Bancassurance Specialist?",
    ],
    escalation=[
        "Opo, nauunawaan ko po. I-transfer ko na po kayo ngayon sa ating insurance financial specialist. Sandali lamang po.",
    ],
    closing=[
        "Maraming salamat po sa inyong oras! Mag-iingat po kayo palagi at magandang araw po!",
    ],
)

PH_MARKET_CONFIG = MarketConfig(
    market=Market.PH,
    sector=Sector.BANCASSURANCE,
    supported_languages=[Language.TAGLISH, Language.FIL, Language.EN],
    default_language=Language.TAGLISH,
    default_register=Register.FORMAL,
    transcriber_config={
        "provider": "deepgram",
        "model": "nova-3",
        "language": "multi",
        "smart_format": True,
        "keywords": [
            "bancassurance:2.0",
            "premium:1.5",
            "policy:1.5",
            "beneficiary:1.5",
            "rider:1.5",
            "lapse:1.5",
            "coverage:1.5",
            "Taglish:1.0",
        ],
    },
    tts_config={
        "provider": "elevenlabs",
        "model": "eleven_multilingual_v2",
        "voice_id": "ph_filipino_female_01",
        "language": "fil",
        "latency_target": 250,
    },
    greeting_style="warm_respectful_taglish_with_po",
    fallback_style="preserve_taglish_with_respect",
    escalation_style="warm_transfer_to_licensed_specialist",
    terminology=PH_TERMINOLOGY_LIST,
    phrasings={
        Language.TAGLISH: PH_TAGLISH_PHRASINGS,
    },
    politeness_particles=["po", "opo", "ho", "kumusta", "salamat"],
)
