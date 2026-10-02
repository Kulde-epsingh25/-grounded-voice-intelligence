"""Tests for LocalizedVoiceAgent execution across Philippines and Indonesia markets."""
import pytest
from app.agents.schemas import ConversationState
from app.localization.agent import LocalizedVoiceAgent
from app.localization.models import Market


class TestLocalizedVoiceAgent:
    def test_ph_agent_cooperative_qualification(self):
        agent = LocalizedVoiceAgent(market=Market.PH, call_id="test-ph-coop")
        turn1 = agent.process_turn("Magandang araw po! May retail grocery business po kami sa Maynila.")
        assert agent.state_machine.current_state == ConversationState.QUALIFICATION
        assert "po" in turn1.assistant_response

        turn2 = agent.process_turn("3 years na po kaming nag-ooperate.")
        assert agent.qualification_manager.state.years_in_business.value == 3.0

        turn3 = agent.process_turn("Ang monthly revenue po namin is around 1.2 million pesos.")
        assert agent.qualification_manager.state.monthly_revenue.value == 1_200_000.0

        turn4 = agent.process_turn("Target po namin is 2 million loan amount.")
        assert agent.qualification_manager.state.requested_amount.value == 2_000_000.0

        turn5 = agent.process_turn("Opo, pumapayag po ako na tawagan ako.")
        assert agent.qualification_manager.state.contact_permission.value is True
        assert agent.lead_created is True
        assert "Magandang balita po" in turn5.assistant_response

    def test_ph_agent_objection_handled_via_kb(self):
        agent = LocalizedVoiceAgent(market=Market.PH, call_id="test-ph-obj")
        turn = agent.process_turn("Worried po ako baka mag-lapse agad kapag na-delay ang payment. Ilang araw ang grace period bago mag-lapse?")
        assert agent.state_machine.current_state == ConversationState.OBJECTION
        assert turn.grounded is True
        assert "31-day grace period" in turn.assistant_response
        assert len(turn.citations_used) > 0

    def test_ph_agent_human_escalation(self):
        agent = LocalizedVoiceAgent(market=Market.PH, call_id="test-ph-esc")
        turn = agent.process_turn("Gusto ko po sanang makausap ang Bancassurance Specialist sa branch.")
        assert agent.state_machine.current_state == ConversationState.ESCALATION
        assert agent.escalated is True
        assert "I-transfer ko na po kayo" in turn.assistant_response

    def test_id_agent_colloquial_qualification(self):
        agent = LocalizedVoiceAgent(market=Market.ID, call_id="test-id-coop")
        turn1 = agent.process_turn("Halo Kak! Mau nanya dana buat usaha kuliner saya.")
        assert "Kak" in turn1.assistant_response

        agent.process_turn("Udah jalan 3 tahun usahanya.")
        assert agent.qualification_manager.state.years_in_business.value == 3.0

        agent.process_turn("Omzet bulanan sekitar 1.2 juta nih.")
        assert agent.qualification_manager.state.monthly_revenue.value == 1_200_000.0

        agent.process_turn("Pengajuan dua juta Kak.")
        assert agent.qualification_manager.state.requested_amount.value == 2_000_000.0

        turn5 = agent.process_turn("Boleh banget Kak, kontak aja via WhatsApp.")
        assert agent.lead_created is True
        assert "Kabar baik Kak" in turn5.assistant_response

    def test_id_agent_objection_handled_via_kb(self):
        agent = LocalizedVoiceAgent(market=Market.ID, call_id="test-id-obj")
        turn = agent.process_turn("Takut denda keterlambatan kemahalan kalau lewat tanggal jatuh tempo. Berapa denda keterlambatan jika melewati jatuh tempo?")
        assert agent.state_machine.current_state == ConversationState.OBJECTION
        assert turn.grounded is True
        assert "0.5%" in turn.assistant_response
        assert len(turn.citations_used) > 0

    def test_id_agent_human_escalation(self):
        agent = LocalizedVoiceAgent(market=Market.ID, call_id="test-id-esc")
        turn = agent.process_turn("Saya ingin berbicara langsung dengan staf customer service atau analis kredit.")
        assert agent.state_machine.current_state == ConversationState.ESCALATION
        assert agent.escalated is True
        assert "customer service" in turn.assistant_response.lower()
