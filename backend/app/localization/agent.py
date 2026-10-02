"""Localized voice agent for Philippines (Bancassurance) and Indonesia (Multifinance)."""
from __future__ import annotations

import re
from typing import Any, Optional
from app.agents.base import VoiceAgent
from app.agents.qualification import QualificationManager
from app.agents.schemas import (
    AgentAction,
    AgentActionType,
    ConversationState,
    QualificationStatus,
    VoiceAgentTurn,
)
from app.agents.state import ConversationStateMachine
from app.agents.tools import (
    create_lead_tool,
    escalate_to_human_tool,
    evaluate_qualification_tool,
    search_knowledge,
)
from app.localization.base import BaseLocalizedAgent
from app.localization.fallback import LocalizedFallbackManager
from app.localization.market import get_market_config
from app.localization.models import (
    Language,
    Market,
    MarketConfig,
    Register,
    TerminologyItem,
)
from app.localization.terminology import ID_TERMINOLOGY, PH_TERMINOLOGY
from app.services.call_events import get_call_event_service


class LocalizedVoiceAgent(BaseLocalizedAgent):
    """Conversational voice agent customized for regional markets with native phrasing."""

    def __init__(
        self,
        market: Market | str = Market.PH,
        call_id: Optional[str] = None,
        initial_language: Optional[Language] = None,
    ):
        config = get_market_config(market)
        super().__init__(market_config=config, call_id=call_id)

        if initial_language:
            self.current_language = initial_language

        self.state_machine = ConversationStateMachine()
        self.qualification_manager = QualificationManager()
        self.turn_index = 0
        self.escalated = False
        self.lead_created = False
        self.detected_terms: list[TerminologyItem] = []
        self.last_detection = None

        # Log call start
        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="call_started",
            payload={
                "market": self.market_config.market.value,
                "sector": self.market_config.sector.value,
                "language": self.current_language.value,
                "register": self.current_register.value,
            },
        )

    def process_turn(self, utterance: str) -> VoiceAgentTurn:
        """Process turn with language detection, terminology recognition, and localized routing."""
        self.turn_index += 1
        state_before = self.state_machine.current_state
        clean_utterance = utterance.strip()
        lower_utt = clean_utterance.lower()

        # 1. Detect language, register, and code-switching
        detection = self.detect_language(clean_utterance)
        self.last_detection = detection

        # 2. Extract domain terminology
        dict_registry = PH_TERMINOLOGY if self.market_config.market == Market.PH else ID_TERMINOLOGY
        matched_terms = dict_registry.find_terms_in_text(clean_utterance)
        self.detected_terms.extend(matched_terms)

        # Log user message with localized context
        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="user_message",
            payload={
                "turn": self.turn_index,
                "text": clean_utterance,
                "market": self.market_config.market.value,
                "language": detection.detected_language.value,
                "register": detection.register.value,
                "code_switch": detection.code_switch_detected,
                "terms": [t.canonical_concept for t in matched_terms],
            },
        )

        actions_taken: list[AgentAction] = []
        citations_used = []
        grounded = True
        assistant_response = ""

        # 3. HUMAN ESCALATION CHECK (English + Localized expressions)
        ph_escalate_phrases = ["makausap", "kinatawan", "taong kausap", "specialist", "agent", "tao", "branch"]
        id_escalate_phrases = ["bicara dengan orang", "staf", "customer service", "manusia", "petugas", "hubungkan ke orang", "ngomong sama orang"]
        en_escalate_phrases = ["human", "representative", "specialist", "agent", "person", "operator", "speak with someone", "talk to someone"]

        active_escalate_phrases = en_escalate_phrases + (
            ph_escalate_phrases if self.market_config.market == Market.PH else id_escalate_phrases
        )

        if any(phrase in lower_utt for phrase in active_escalate_phrases):
            self.state_machine.transition(ConversationState.ESCALATION, reason="Caller requested human")
            esc_res = escalate_to_human_tool(self.call_id, reason="Caller explicit request")
            actions_taken.append(AgentAction(action_type=AgentActionType.ESCALATE, result=esc_res))
            assistant_response = LocalizedFallbackManager.get_fallback(
                market=self.market_config.market,
                language=self.current_language,
                reason="human_escalation",
                register=self.current_register,
            )
            self.escalated = True

        # 4. OBJECTION CHECK (e.g. price/premium objection, tenor/cicilan objection)
        elif self._is_objection(lower_utt):
            self.state_machine.transition(ConversationState.OBJECTION, reason="Customer raised objection")
            # Extract focused query clause if multi-sentence
            kb_query = self._extract_kb_query(clean_utterance)
            kb_res = search_knowledge(kb_query, filters={"market": self.market_config.market.value})
            actions_taken.append(
                AgentAction(action_type=AgentActionType.SEARCH_KB, parameters={"query": kb_query}, result=kb_res)
            )

            if kb_res["grounded"]:
                citations_used = kb_res["citations"]
                if self.market_config.market == Market.PH:
                    assistant_response = (
                        f"Nauunawaan ko po ang inyong pag-aalala. {kb_res['answer']}\n\n"
                        "Gusto niyo po bang i-check natin ang iba pang flexible payment plans para dito?"
                    )
                else:
                    if self.current_register == Register.COLLOQUIAL:
                        assistant_response = (
                            f"Paham banget Kak kekhawatiran Kakak. {kb_res['answer']}\n\n"
                            "Gimana kalau kita sesuaikan tenornya biar cicilannya lebih pas di kantong?"
                        )
                    else:
                        assistant_response = (
                            f"Dapat kami pahami pertimbangan Bapak/Ibu. {kb_res['answer']}\n\n"
                            "Apakah berkenan kami carikan simulasi dengan tenor yang lebih panjang agar angsuran tetap terjangkau?"
                        )
            else:
                grounded = False
                fallback_msg = self.get_localized_fallback("unsupported_kb")
                assistant_response = fallback_msg

        # 5. KNOWLEDGE QUESTION CHECK (terms, rates, coverage, documents, requirements)
        elif self._is_knowledge_question(lower_utt):
            self.state_machine.transition(ConversationState.KNOWLEDGE_QUESTION, reason="Information inquiry")
            kb_query = self._extract_kb_query(clean_utterance)
            kb_res = search_knowledge(kb_query, filters={"market": self.market_config.market.value})
            actions_taken.append(
                AgentAction(action_type=AgentActionType.SEARCH_KB, parameters={"query": kb_query}, result=kb_res)
            )

            if kb_res["grounded"]:
                citations_used = kb_res["citations"]
                assistant_response = kb_res["answer"]
            else:
                grounded = False
                assistant_response = self.get_localized_fallback("unsupported_kb")

        # 6. QUALIFICATION INFORMATION FLOW
        else:
            if self.state_machine.current_state in (ConversationState.GREETING, ConversationState.UNDERSTAND_INTENT):
                self.state_machine.transition(ConversationState.QUALIFICATION, reason="Started qualification profile")

            extracted = self._extract_localized_fields(clean_utterance)
            for k, v in extracted.items():
                f_obj = self.qualification_manager.update_field(k, v, turn_index=self.turn_index)
                get_call_event_service().log_event(
                    call_id=self.call_id,
                    event_type="qualification_update",
                    payload={"field": k, "value": f_obj.value, "ambiguous": f_obj.is_ambiguous},
                )

            # Ambiguity check
            ambiguous_fields = [
                f for f in [
                    self.qualification_manager.state.monthly_revenue,
                    self.qualification_manager.state.requested_amount,
                ] if f and f.is_ambiguous
            ]

            if ambiguous_fields:
                assistant_response = self._get_clarification_prompt(ambiguous_fields[0].name)
            else:
                eval_res = evaluate_qualification_tool(
                    self.qualification_manager.state.to_dict(),
                    turn_index=self.turn_index,
                )
                actions_taken.append(AgentAction(action_type=AgentActionType.EVALUATE_QUALIFICATION, result=eval_res))

                status = eval_res["status"]
                if status == QualificationStatus.NEEDS_MORE_INFORMATION.value:
                    missing = eval_res["missing_fields"]
                    assistant_response = self._get_missing_field_prompt(missing[0])
                elif status == QualificationStatus.ELIGIBLE.value:
                    prod = eval_res["recommended_product"]
                    max_amt = eval_res["max_eligible_amount"]
                    rate = eval_res["interest_rate"]
                    self.state_machine.transition(ConversationState.REVIEW, reason="All criteria met")
                    assistant_response = self._format_eligible_response(prod, max_amt, rate)

                    lead_res = create_lead_tool(
                        call_id=self.call_id,
                        fields=self.qualification_manager.state.to_dict(),
                        qualification_status="ELIGIBLE",
                        recommended_product=prod,
                        contact_permission=True,
                        notes=f"Qualified via localized bot ({self.market_config.market.value})",
                    )
                    actions_taken.append(AgentAction(action_type=AgentActionType.CREATE_LEAD, result=lead_res))
                    self.lead_created = True
                elif status == QualificationStatus.MANUAL_REVIEW.value:
                    self.state_machine.transition(ConversationState.REVIEW, reason="Requires review")
                    assistant_response = self._format_manual_review_response(eval_res["reasons"][0])
                    lead_res = create_lead_tool(
                        call_id=self.call_id,
                        fields=self.qualification_manager.state.to_dict(),
                        qualification_status="MANUAL_REVIEW",
                        notes=eval_res["reasons"][0],
                    )
                    actions_taken.append(AgentAction(action_type=AgentActionType.CREATE_LEAD, result=lead_res))
                    self.lead_created = True
                else:
                    self.state_machine.transition(ConversationState.REVIEW, reason="Ineligible")
                    assistant_response = self._format_ineligible_response(eval_res["reasons"][0])

        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="assistant_message",
            payload={"turn": self.turn_index, "text": assistant_response},
        )

        return VoiceAgentTurn(
            turn_index=self.turn_index,
            user_utterance=clean_utterance,
            assistant_response=assistant_response,
            state_before=state_before,
            state_after=self.state_machine.current_state,
            actions_taken=actions_taken,
            grounded=grounded,
            citations_used=citations_used,
        )

    def get_localized_fallback(self, reason: str = "unsupported_kb") -> str:
        """Retrieve fallback message preserving language and register."""
        return LocalizedFallbackManager.get_fallback(
            market=self.market_config.market,
            language=self.current_language,
            reason=reason,
            register=self.current_register,
        )

    def _is_objection(self, text: str) -> bool:
        ph_objections = [
            "mahal", "mataas ang premium", "hindi ko kaya", "may insurance na",
            "pag-iisipan", "too expensive", "worried", "alala", "baka mag-lapse", "mag-lapse"
        ]
        id_objections = [
            "kemahalan", "bunganya tinggi", "denda terlalu besar", "tenor kepanjangan",
            "pikir-pikir", "dp-nya berat", "denda keterlambatan", "takut denda", "denda"
        ]
        common = ["too long", "too high", "why do i need", "ridiculous", "cannot provide"]

        pool = common + (ph_objections if self.market_config.market == Market.PH else id_objections)
        return any(phrase in text for phrase in pool)

    def _is_knowledge_question(self, text: str) -> bool:
        ph_q = ["ano", "paano", "magkano", "kailan", "pwede ba", "mayroon ba", "saan", "ilang", "bakit", "alin"]
        id_q = ["apa", "bagaimana", "gimana", "berapa", "kapan", "apakah", "bisa nggak", "di mana", "kenapa", "mengapa"]
        en_q = ["what", "how", "can i", "do you", "which", "where", "is there", "why"]

        pool = en_q + (ph_q if self.market_config.market == Market.PH else id_q)
        return any(text.startswith(w) for w in pool) or "?" in text

    def _extract_localized_fields(self, text: str) -> dict[str, Any]:
        """Extract qualification fields supporting English, Tagalog, and Indonesian number words."""
        fields: dict[str, Any] = {}
        lower = text.lower()

        # Business / profession type
        types = [
            "retail", "restaurant", "manufacturing", "construction", "technology", "logistics",
            "trading", "healthcare", "usaha toko", "bengkel", "kuliner", "karyawan", "pns", "freelance"
        ]
        for btype in types:
            if btype in lower:
                fields["business_type"] = btype

        # Years in business / work
        year_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?|taon|tahun)\b", lower)
        if year_match:
            fields["years_in_business"] = year_match.group(1)

        # Revenue / income
        # Handles "1.2 million", "1.2 juta", "500k", "500 ribu", "50 juta", "50k", "fifty"
        rev_match = re.search(
            r"(?:monthly\s+revenue|revenue|income|gaji|penghasilan|omzet|kita|kinikita)\b.*?\b([0-9\.]+\s*(?:thousand|million|juta|jt|ribu|rb|k|m)?)\b",
            lower,
        )
        if rev_match and rev_match.group(1).strip() not in ("of", "is", "around", "about", "revenue", "income", "a", "an", "the", "gaji", "omzet", "po"):
            cand = rev_match.group(1).strip()
            if "juta" in cand or "jt" in cand:
                num = re.findall(r"[\d\.]+", cand)
                if num:
                    fields["monthly_revenue"] = str(float(num[0]) * 1_000_000)
            elif "ribu" in cand or "rb" in cand:
                num = re.findall(r"[\d\.]+", cand)
                if num:
                    fields["monthly_revenue"] = str(float(num[0]) * 1_000)
            else:
                fields["monthly_revenue"] = cand
        elif any(w in lower for w in ["fifty", "lima puluh", "limampu", "forty"]):
            fields["monthly_revenue"] = "fifty"

        # Requested amount / loan / coverage amount
        word_numbers = {
            "satu": 1.0, "dua": 2.0, "tiga": 3.0, "empat": 4.0, "lima": 5.0,
            "isa": 1.0, "dalawa": 2.0, "tatlo": 3.0, "apat": 4.0,
            "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0,
        }
        for w, val in word_numbers.items():
            if f"{w} juta" in lower or f"{w} jt" in lower or f"{w} million" in lower:
                fields["requested_amount"] = str(val * 1_000_000)
                break
            elif f"{w} ribu" in lower or f"{w} rb" in lower or f"{w} thousand" in lower:
                fields["requested_amount"] = str(val * 1_000)
                break

        if "requested_amount" not in fields:
            amt_match = re.search(
                r"(?:loan\s*amount|borrow|loan\s*of|request(?:ing)?|need\s*to\s*borrow|need|pinjam|pengajuan|coverage|plafon|target)\b.*?\b([0-9\.]+\s*(?:thousand|million|juta|jt|ribu|rb|k|m)?)\b",
                lower,
            )
            if amt_match and amt_match.group(1).strip() not in ("of", "a", "for", "to", "amount", "loan", "borrow", "pinjam", "po"):
                cand = amt_match.group(1).strip()
                if "juta" in cand or "jt" in cand:
                    num = re.findall(r"[\d\.]+", cand)
                    if num:
                        fields["requested_amount"] = str(float(num[0]) * 1_000_000)
                elif "ribu" in cand or "rb" in cand:
                    num = re.findall(r"[\d\.]+", cand)
                    if num:
                        fields["requested_amount"] = str(float(num[0]) * 1_000)
                else:
                    fields["requested_amount"] = cand

        # Contact permission
        perm_words = [
            "permission", "contact me", "proceed", "agree", "consent",
            "yes", "oo", "opo", "payag", "sige", "boleh", "bisa", "bersedia", "setuju", "ya"
        ]
        if any(w in lower for w in perm_words):
            fields["contact_permission"] = "yes"

        return fields

    def _extract_kb_query(self, text: str) -> str:
        """Extract the most relevant question clause from a complex utterance."""
        clauses = re.split(r"[\.\?\!]", text)
        # 1. First look for an explicit question clause
        for c in clauses:
            clean_c = c.strip()
            if len(clean_c) >= 10 and self._is_knowledge_question(clean_c.lower()):
                return clean_c

        # 2. Second look for domain keyword clauses
        for c in clauses:
            clean_c = c.strip()
            if len(clean_c) >= 10 and any(
                w in clean_c.lower() for w in ["grace period", "denda", "cicilan", "tenor", "dp", "lapse", "premium", "rider", "jatuh tempo"]
            ):
                return clean_c

        return text

    def _get_missing_field_prompt(self, field_name: str) -> str:
        """Retrieve localized prompt for the next missing qualification attribute."""
        if self.market_config.market == Market.PH:
            prompts = {
                "business_type": "Ano po ang kasalukuyang negosyo o propesyon ninyo ngayon?",
                "years_in_business": "Ilang taon na po kayong nagpapatakbo ng inyong negosyo?",
                "monthly_revenue": "Mga magkano po ang average na monthly revenue o kinikita ninyo kada buwan?",
                "requested_amount": "Magkano po ang target coverage o halaga na nais ninyong i-secure?",
                "contact_permission": "Pumapayag po ba kayo na tawagan kayo ng ating Bancassurance Specialist para sa inyong proposal?",
            }
        else:
            if self.current_register == Register.COLLOQUIAL:
                prompts = {
                    "business_type": "Saat ini lagi usaha di bidang apa atau kerja sebagai apa nih, Kak?",
                    "years_in_business": "Udah berapa lama nih usahanya atau kerja di tempat yang sekarang, Kak?",
                    "monthly_revenue": "Kira-kira rata-rata pemasukan atau gaji per bulan berapa ya, Kak?",
                    "requested_amount": "Rencana mau ngajuin pinjaman berapa juta nih, Kak?",
                    "contact_permission": "Boleh ya Kak kalau nanti tim staf kami hubungi via WhatsApp atau telepon?",
                }
            else:
                prompts = {
                    "business_type": "Boleh diinformasikan jenis pekerjaan atau bidang usaha yang sedang Bapak/Ibu jalankan saat ini?",
                    "years_in_business": "Sudah berapa lama bidang usaha atau masa kerja Bapak/Ibu berjalan?",
                    "monthly_revenue": "Berapa rata-rata penghasilan kotor atau omzet bulanan yang diperoleh setiap bulannya?",
                    "requested_amount": "Berapa estimasi nominal pembiayaan yang ingin Bapak/Ibu ajukan?",
                    "contact_permission": "Apakah Bapak/Ibu menyetujui jika staf konsultan kami menghubungi kembali untuk menyampaikan rincian cicilan?",
                }
        return prompts.get(field_name, "Could you provide more details regarding that?")

    def _get_clarification_prompt(self, field_name: str) -> str:
        if self.market_config.market == Market.PH:
            return "Pasensya na po, maaari po bang pakilinaw kung limampung libo o limang daang libong piso po ba ang tinutukoy ninyo?"
        else:
            if self.current_register == Register.COLLOQUIAL:
                return "Boleh diperjelas lagi nggak Kak nominalnya, maksudnya lima puluh juta apa lima juta rupiah nih?"
            else:
                return "Mohon maaf Bapak/Ibu, apakah yang dimaksud adalah lima puluh juta atau lima ratus juta rupiah?"

    def _format_eligible_response(self, product: str, max_amt: float, rate: float) -> str:
        if self.market_config.market == Market.PH:
            return (
                f"Magandang balita po! Pasok po ang inyong profile sa ating {product} plan. "
                f"Qualified po kayo para sa hanggang ${max_amt:,.0f} sa interest rate na {rate:.1f}%. "
                "Na-record ko na po ang inyong application lead para ma-assist kayo ng ating specialist sa branch."
            )
        else:
            if self.current_register == Register.COLLOQUIAL:
                return (
                    f"Kabar baik Kak! Pengajuan Kakak cocok banget nih sama produk {product} kami. "
                    f"Plafon maksimalnya bisa sampai Rp {max_amt:,.0f} dengan bunga {rate:.1f}% aja. "
                    "Datanya udah aku simpan ya, nanti tim staf kami bakal langsung kontak Kakak buat proses lanjutannya."
                )
            else:
                return (
                    f"Kabar baik Bapak/Ibu, permohonan Anda memenuhi kriteria untuk produk pembiayaan {product}. "
                    f"Anda berhak mendapatkan fasilitas hingga Rp {max_amt:,.0f} dengan suku bunga {rate:.1f}%. "
                    "Data pengajuan Anda telah kami teruskan kepada konsultan pembiayaan kami untuk penyusunan jadwal cicilan resmi."
                )

    def _format_manual_review_response(self, reason: str) -> str:
        if self.market_config.market == Market.PH:
            return f"Maraming salamat po. Ang inyong request ay kailangan pong i-review ng ating senior underwriter dahil: {reason}"
        else:
            return f"Terima kasih. Permohonan Anda memerlukan peninjauan lanjutan oleh staf analis kredit kami karena: {reason}"

    def _format_ineligible_response(self, reason: str) -> str:
        if self.market_config.market == Market.PH:
            return f"Salamat po sa pagbibigay ng impormasyon. Sa ngayon po ay hindi pa pasok ang profile dahil: {reason}"
        else:
            return f"Terima kasih atas informasinya. Saat ini permohonan belum dapat disetujui karena: {reason}"
