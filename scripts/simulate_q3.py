"""Simulation runner for Q3 localized voice bots (Philippines and Indonesia).

Executes multi-turn conversation scenarios, records linguistic/register metadata,
generates ASR/TTS evaluation manifests, and creates audit evidence in evidence/q3/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.integrations.tts.client import TTSClient
from app.integrations.tts.models import TTSConfig
from app.integrations.vapi.assistant import (
    build_indonesia_assistant,
    build_philippines_assistant,
)
from app.localization.agent import LocalizedVoiceAgent
from app.localization.evaluation import evaluate_asr_manifest
from app.localization.indonesia import ID_LOCALIZATION_EXAMPLES, ID_MARKET_CONFIG
from app.localization.models import Market
from app.localization.philippines import PH_LOCALIZATION_EXAMPLES, PH_MARKET_CONFIG


def run_localized_scenario(
    market: Market,
    scenario_id: str,
    name: str,
    description: str,
    turns: list[str],
) -> dict:
    """Run an interactive conversation scenario through LocalizedVoiceAgent."""
    call_id = f"sim-{market.value.lower()}-{scenario_id}"
    agent = LocalizedVoiceAgent(market=market, call_id=call_id)
    history = []

    for turn_idx, text in enumerate(turns, start=1):
        turn = agent.process_turn(text)
        history.append({
            "turn": turn_idx,
            "caller": text,
            "agent": turn.assistant_response,
            "detected_language": agent.current_language.value,
            "detected_register": agent.current_register.value,
            "code_switch_detected": agent.detected_code_switch,
            "state_before": turn.state_before.value,
            "state_after": turn.state_after.value,
            "grounded": turn.grounded,
            "citations": turn.citations_used,
            "actions": [
                {
                    "action_type": a.action_type.value,
                    "parameters": a.parameters,
                    "result_summary": a.result.get("status") or a.result.get("result") or ("grounded" if a.result.get("grounded") else "ungrounded"),
                }
                for a in turn.actions_taken
            ],
        })

    return {
        "scenario_id": scenario_id,
        "name": name,
        "description": description,
        "call_id": call_id,
        "call_type": "SIMULATION — NOT LIVE CALL",
        "market": market.value,
        "final_language": agent.current_language.value,
        "final_register": agent.current_register.value,
        "final_state": agent.state_machine.current_state.value,
        "qualification_state": agent.qualification_manager.state.to_dict(),
        "lead_created": agent.lead_created,
        "escalated": agent.escalated,
        "detected_terminology": list({t.canonical_concept for t in agent.detected_terms}),
        "transcript": history,
    }


def main():
    root = Path(__file__).resolve().parent.parent
    q3_dir = root / "evidence" / "q3"
    ph_dir = q3_dir / "philippines"
    id_dir = q3_dir / "indonesia"
    reg_dir = q3_dir / "regional"
    config_dir = root / "config"

    ph_dir.mkdir(parents=True, exist_ok=True)
    id_dir.mkdir(parents=True, exist_ok=True)
    reg_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SIMULATING Q3 LOCALIZED CONVERSATION SCENARIOS")
    print("=" * 60)

    # -------------------------------------------------------------
    # 1. PHILIPPINES SCENARIOS
    # -------------------------------------------------------------
    ph_scenarios = [
        {
            "id": "CALL-PH-01",
            "name": "Cooperative Bancassurance Client (Taglish)",
            "desc": "Customer inquires and qualifies for bancassurance life coverage in natural Taglish.",
            "turns": [
                "Magandang araw po! May retail grocery business po ako sa Quezon City.",
                "Nasa 3 years na po kaming nag-ooperate.",
                "Ang monthly revenue po namin is around 1.2 million pesos.",
                "Target po naming loan or coverage amount is 2 million para sa protection.",
                "Opo, pumapayag po ako na tawagan ako ng specialist niyo sa branch.",
            ],
        },
        {
            "id": "CALL-PH-02",
            "name": "Sector-Specific Objection (Lapse & Grace Period)",
            "desc": "Customer worries about policy lapse if premium payment is delayed. Agent resolves via Q2 KB.",
            "turns": [
                "Hello po, interested po ako sa life plan pero worried ako baka mag-lapse agad kapag na-delay ang sweldo ko.",
                "Ilang araw po ba ang grace period bago mag-lapse ang policy?",
                "Sige po, 3 years na akong working as technology consultant with 1.5 million revenue.",
            ],
        },
        {
            "id": "CALL-PH-03",
            "name": "Mixed Taglish with Human Escalation",
            "desc": "Customer requests immediate human transfer to speak with a licensed branch specialist.",
            "turns": [
                "Good morning po, gusto ko po sanang magpa-assist sa licensed Bancassurance Specialist sa branch para sa estate planning.",
            ],
        },
    ]

    for idx, sc in enumerate(ph_scenarios, start=1):
        res = run_localized_scenario(
            market=Market.PH,
            scenario_id=sc["id"],
            name=sc["name"],
            description=sc["desc"],
            turns=sc["turns"],
        )
        call_file = ph_dir / f"call-0{idx}.json"
        with open(call_file, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        print(f"Generated PH Call: {call_file.name}")

    # PH Localization Examples
    ph_examples_data = [e.model_dump(mode="json") for e in PH_LOCALIZATION_EXAMPLES]
    with open(ph_dir / "localization_examples.json", "w", encoding="utf-8") as f:
        json.dump(ph_examples_data, f, indent=2)

    # PH ASR evaluation manifest
    ph_asr_summary = evaluate_asr_manifest(root / "data" / "eval" / "q3_asr" / "philippines.json")
    with open(ph_dir / "asr_results.json", "w", encoding="utf-8") as f:
        json.dump(ph_asr_summary.model_dump(mode="json"), f, indent=2)

    # PH TTS generation record
    tts_client = TTSClient()
    ph_tts_rec = tts_client.synthesize_or_manifest(
        text="Magandang araw po! Ako po ang inyong Bancassurance Virtual Assistant mula sa partner bank.",
        config=TTSConfig(voice_id="21m00Tcm4TlvDq8ikWAM", language="fil"),
        market="PH",
    )
    with open(ph_dir / "tts_results.json", "w", encoding="utf-8") as f:
        json.dump(ph_tts_rec.model_dump(mode="json"), f, indent=2)

    # PH Vapi Assistant Config
    ph_asst_cfg = build_philippines_assistant("http://localhost:8000")
    ph_cfg_dict = ph_asst_cfg.model_dump(mode="json")
    ph_cfg_dict["_notice"] = "CONFIG_ONLY — NOT DEPLOYED (NO VAPI API KEY)"
    with open(ph_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(ph_cfg_dict, f, indent=2)
    with open(config_dir / "vapi_philippines.json", "w", encoding="utf-8") as f:
        json.dump(ph_cfg_dict, f, indent=2)

    # -------------------------------------------------------------
    # 2. INDONESIA SCENARIOS
    # -------------------------------------------------------------
    id_scenarios = [
        {
            "id": "CALL-ID-01",
            "name": "Cooperative Consumer Finance Client (Colloquial)",
            "desc": "Customer inquires about consumer financing with friendly colloquial Indonesian.",
            "turns": [
                "Halo Kak! Mau nanya dong soal pembiayaan dana buat usaha kuliner saya.",
                "Usahanya udah jalan 3 tahun nih Kak.",
                "Rata-rata omzet bulanan kita sekitar 1.2 juta.",
                "Rencana mau ngajuin pinjaman dua juta buat nambah alat masak.",
                "Boleh banget Kak, silakan kalau tim staf mau hubungi saya via WA.",
            ],
        },
        {
            "id": "CALL-ID-02",
            "name": "Finance Objection with English Terminology (DP & Denda)",
            "desc": "Customer objects to late penalties and down payment. Grounded in Q2 KB.",
            "turns": [
                "Siang Kak, mau cek kredit motor tapi takut denda keterlambatannya kemahalan kalau lewat tanggal jatuh tempo.",
                "Berapa denda keterlambatan jika melewati tanggal jatuh tempo?",
                "Usaha bengkel saya udah 3 tahun, omzet 1.5 juta per bulan.",
            ],
        },
        {
            "id": "CALL-ID-03",
            "name": "Formal Indonesian with Human Escalation",
            "desc": "Customer requests immediate escalation to customer service officer.",
            "turns": [
                "Selamat pagi Bapak/Ibu, saya ingin berbicara dengan staf customer service langsung terkait restrukturisasi kredit pembiayaan saya.",
            ],
        },
    ]

    for idx, sc in enumerate(id_scenarios, start=1):
        res = run_localized_scenario(
            market=Market.ID,
            scenario_id=sc["id"],
            name=sc["name"],
            description=sc["desc"],
            turns=sc["turns"],
        )
        call_file = id_dir / f"call-0{idx}.json"
        with open(call_file, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        print(f"Generated ID Call: {call_file.name}")

    # ID Localization Examples
    id_examples_data = [e.model_dump(mode="json") for e in ID_LOCALIZATION_EXAMPLES]
    with open(id_dir / "localization_examples.json", "w", encoding="utf-8") as f:
        json.dump(id_examples_data, f, indent=2)

    # ID ASR evaluation manifest
    id_asr_summary = evaluate_asr_manifest(root / "data" / "eval" / "q3_asr" / "indonesia.json")
    with open(id_dir / "asr_results.json", "w", encoding="utf-8") as f:
        json.dump(id_asr_summary.model_dump(mode="json"), f, indent=2)

    # ID Regional Accent Manifest
    with open(root / "data" / "eval" / "q3_asr" / "indonesia_regional.json", "r", encoding="utf-8") as f:
        reg_data = json.load(f)
    with open(reg_dir / "accent_test_manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "status": "TEST CASE PREPARED — AUDIO NOT YET AVAILABLE",
            "manifest": reg_data,
        }, f, indent=2)

    # ID TTS generation record
    id_tts_rec = tts_client.synthesize_or_manifest(
        text="Selamat pagi Bapak/Ibu, terima kasih telah menghubungi layanan pembiayaan kami.",
        config=TTSConfig(voice_id="AZnzlk1XvdvUeBnXmlld", language="id"),
        market="ID",
    )
    with open(id_dir / "tts_results.json", "w", encoding="utf-8") as f:
        json.dump(id_tts_rec.model_dump(mode="json"), f, indent=2)

    # ID Vapi Assistant Config
    id_asst_cfg = build_indonesia_assistant("http://localhost:8000")
    id_cfg_dict = id_asst_cfg.model_dump(mode="json")
    id_cfg_dict["_notice"] = "CONFIG_ONLY — NOT DEPLOYED (NO VAPI API KEY)"
    with open(id_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(id_cfg_dict, f, indent=2)
    with open(config_dir / "vapi_indonesia.json", "w", encoding="utf-8") as f:
        json.dump(id_cfg_dict, f, indent=2)

    print("=" * 60)
    print("Q3 EVIDENCE AND SIMULATION ARTIFACTS GENERATED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
