# Q3: Native-Language Voice Bots (Philippines & Indonesia)

## 1. Architecture

The Q3 native-language voice architecture builds directly on top of the Q1 base conversational state machine, tool webhook infrastructure, and Q2 hybrid retrieval layer without code duplication or secondary vector databases.

```
                          ┌────────────────────────┐
                          │   Base Voice Agent     │
                          │   (State & Tools)      │
                          └───────────┬────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
        ┌───────────────────────┐             ┌───────────────────────┐
        │  Philippines Market   │             │   Indonesia Market    │
        │  (Bancassurance)      │             │   (Multifinance)      │
        └──────────┬────────────┘             └──────────┬────────────┘
                   │                                     │
         ┌─────────┼─────────┐                 ┌─────────┼─────────┐
         ▼         ▼         ▼                 ▼         ▼         ▼
      English   Tagalog   Taglish           Formal   Colloquial  Mixed Loanwords
         │         │         │                 │         │         │
         └─────────┼─────────┘                 └─────────┼─────────┘
                   ▼                                     ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                 Shared Localization Core                    │
        │  - MarketConfig / LanguageConfig (models.py)                │
        │  - TerminologyDictionary (terminology.py)                   │
        │  - Heuristic Language & Register Detector (language.py)     │
        │  - Safe Localized Fallback Policy (fallback.py)             │
        │  - LocalizedVoiceAgent (agent.py)                           │
        └──────────────────────────────┬──────────────────────────────┘
                                       │
                                       ▼
        ┌─────────────────────────────────────────────────────────────┐
        │             Q2 Knowledge Base (/kb/search)                  │
        │  - dense + BM25 hybrid retrieval                            │
        │  - metadata filters: market (PH/ID), sector, language       │
        │  - confidence gate (>= 0.60) & verifiable citations         │
        └──────────────────────────────┬──────────────────────────────┘
                                       │
                                       ▼
        ┌─────────────────────────────────────────────────────────────┐
        │               Provider Integration Layer                    │
        │  - ASR: Vapi + Deepgram Nova 3 (language: "multi")          │
        │  - TTS: ElevenLabs Multilingual v2 (fil / id presets)       │
        └─────────────────────────────────────────────────────────────┘
```

### Core Architecture Components (`backend/app/localization/`)
1. **`models.py`**: Immutable domain models for `Market`, `Language`, `Sector`, `Register`, `TerminologyItem`, `LanguageDetectionResult`, `LocalizationExample`, `LocalizedPhrasingSet`, and `MarketConfig`.
2. **`terminology.py`**: Domain-specific term registries mapping customer loanwords and colloquialisms to canonical concepts with bidirectional variant resolution.
3. **`language.py`**: Heuristic language and register detection tracking language, register, code-switching triggers, and confidence score.
4. **`fallback.py`**: Contextual fallback engine ensuring conversational turns never inadvertently revert to English when handling unsupported knowledge questions, ASR dropouts, or escalation.
5. **`agent.py`**: `LocalizedVoiceAgent` extending the Q1 state machine with localized phrasing, query extraction, rule qualification, and Q2 grounding.
6. **`philippines.py` & `indonesia.py`**: Complete market configuration definitions.
7. **`evaluation.py`**: Automated evaluation harness measuring ASR accuracy, terminology hit rate, and code-switch detection over test manifests.

---

## 2. Philippines Configuration (`backend/app/localization/philippines.py`)

- **Market**: `PH` (Philippines)
- **Sector**: `life_insurance_or_bancassurance`
- **Supported Languages**: English (`en`), Filipino/Tagalog (`fil`), Taglish (`taglish`)
- **Default Language**: `taglish` (reflecting actual metropolitan consumer speech)
- **Conversational Register**: `respectful_consultative`
- **Primary Implemented Flow**: **Bancassurance Policy Protection & Grace Period Inquiry**
  - *Rationale*: Metro Manila and provincial bank customers frequently receive policy notifications linked to bank accounts. Customers experience acute anxiety regarding policy lapse, payment grace periods, and rider protections. The agent must balance reassuring politeness (`po`/`opo`) with precise insurance terms.

### Greeting & Persona
- Uses polite opening with bank affiliation and respectful honorifics:
  `"Magandang araw po! Ako po ang inyong bancassurance specialist. Kumusta po kayo ngayon?"`
- Reassurance and permission:
  `"May ilang minuto po ba kayo para pag-usapan ang protection coverage ng inyong active policy?"`

---

## 3. Indonesia Configuration (`backend/app/localization/indonesia.py`)

- **Market**: `ID` (Indonesia)
- **Sector**: `multifinance_or_consumer_finance`
- **Supported Languages**: Formal Indonesian (`id_formal`), Colloquial Indonesian (`id_colloquial`), Mixed/Loanword Indonesian (`id_mixed`)
- **Default Language**: `id_formal`
- **Conversational Register**: `professional_empathetic`
- **Primary Implemented Flow**: **Consumer Multifinance Vehicle/Electronics Installment & Restructuring Inquiry**
  - *Rationale*: Multifinance represents Indonesia's dominant retail lending channel. Borrowers routinely inquire about monthly installments (`cicilan`), down payments (`DP`), payment terms (`tenor`), grace periods (`jatuh tempo`), and late penalty fees (`denda`). The bot must navigate the cultural boundary between formal business respect (`Bapak/Ibu`) and conversational mobile chat tone (`Kak/kamu`).

### Greeting & Persona
- **Formal Register**:
  `"Selamat siang, Bapak/Ibu. Saya asisten virtual dari layanan multifinance. Ada yang bisa saya bantu terkait pembiayaan Anda hari ini?"`
- **Colloquial Register**:
  `"Halo Kak! Ada yang bisa kami bantu buat cek cicilan atau pengajuan tenor hari ini?"`

---

## 4. Localization Approach vs Literal Translation

Literal translation produces robotic, culturally inappropriate, and unintelligible voice interactions. Real voice bots must account for cultural deference, local bureaucratic conventions, and everyday conversational markers.

### Philippines: Cultural & Linguistic Adaptation
1. **Politeness Markers (`po` / `opo`)**: Crucial in Filipino customer service. Omitting them conveys bluntness, disrespect, or irritation.
2. **Consultative Framing**: In Filipino culture, financial insecurity is sensitive. Instead of demanding *"Magbayad ka na bago mag-lapse"* (literal: Pay now before it lapses), the bot uses consultative phrasing: *"Para po maprotektahan ang inyong coverage at hindi mag-lapse ang policy, pwede po nating i-check ang grace period options ninyo."*
3. **English Borrowing Preference**: Technical insurance concepts (`grace period`, `policy lapse`, `rider coverage`, `beneficiary`) are never translated to obscure coined Tagalog equivalents (*"panahon ng palugit"*, *"tagapagpakinabang"*). Real bank clients use English insurance terms embedded in Tagalog syntax.

### Indonesia: Cultural & Linguistic Adaptation
1. **Pronoun and Honorific Hierarchy**: 
   - Formal banking/multifinance mandates `Bapak` (Mr.) / `Ibu` (Mrs./Ms.).
   - Colloquial digital fintech commonly utilizes `Kak` (sibling/peer).
   - Second-person pronoun `Anda` is used respectfully; `kamu` is reserved for casual youth interactions.
2. **Loanword Naturalization**: English words are loanwords adopted into Indonesian syntax: *"Bisa tolong jelaskan detail down payment dan biaya adminnya?"*
3. **Face-Saving Inquiries**: Discussing late payments (`denda keterlambatan`) or overdue accounts requires soft indirect phrasing (*"mengingatkan jadwal jatuh tempo"* rather than aggressive collections rhetoric).

---

## 5. Code-Switch Strategy (Taglish & Indonesian Mixed)

### Taglish Code-Switch Patterns
Taglish is not arbitrary word salad. It follows well-defined linguistic patterns:
1. **Tagalog Morphological Affixation with English Verbs**:
   - `mag-` prefix: `mag-apply`, `mag-lapse`, `mag-renew`
   - `i-` prefix: `i-check`, `i-forward`, `i-upgrade`
   - `na-` prefix: `na-receive`, `na-process`
2. **Matrix Language Frame**: Tagalog serves as the matrix grammatical structure with English technical nouns plugged in:
   `"Gusto ko lang i-check kung covered pa ang policy ko kapag may emergency hospitalization."`
3. **Discourse Connectors**: Interjections and discourse particles maintain conversational rhythm (`kasi po`, `talaga`, `so bale`).

### Indonesian Code-Switch & Loanword Patterns
1. **Finance Domain Terms**:
   - `DP` / `down payment`, `tenor`, `approval`, `take over`, `leasing`, `survey`, `admin fee`.
2. **Sentence Construction**:
   `"Untuk pengajuan cicilan motor ini, butuh approval berapa hari kerja ya setelah survey?"`

---

## 6. Terminology Dictionaries (`backend/app/localization/terminology.py`)

The terminology dictionary standardizes raw spoken vocabulary, customer slang, and regional abbreviations into canonical concepts recognized by deterministic rules and retrieval queries.

### Canonical Terminology Mapping Matrix

| Market | Canonical Concept | Spoken / Localized Variants | Domain / Sector | Cultural Notes |
|--------|-------------------|-----------------------------|-----------------|----------------|
| **PH** | `premium` | hulog, bayad, monthly premium, regular contribution | Bancassurance | Bank clients interchange "hulog sa bangko" with premium |
| **PH** | `policy` | polis, seguro, life plan, active policy | Bancassurance | "Polis" is historical; "policy" or "plan" dominates metro usage |
| **PH** | `beneficiary` | tagapagmana, benepisyaryo, dependent, beneficiary | Bancassurance | Legal documents use "benepisyaryo"; clients say "beneficiary" |
| **PH** | `rider` | dagdag-proteksyon, additional benefit, rider coverage | Bancassurance | Critical illness/accident add-ons |
| **PH** | `lapse` | mapaso, mawalan ng bisa, mag-lapse, overdue cancellation | Bancassurance | "Mag-lapse" is the ubiquitous Taglish conversational phrase |
| **PH** | `coverage` | proteksyon, sakop, insurance coverage | Bancassurance | Scope of sum assured and claimable benefits |
| **PH** | `bank referral` | referral ng branch, endorsement ng bangko, bank specialist | Bancassurance | Cross-sell conduit between bank teller and insurance rep |
| **ID** | `installment` | cicilan, angsuran, pembayaran bulanan, cicil | Multifinance | "Angsuran" is formal legal; "cicilan" is standard retail |
| **ID** | `tenor` | jangka waktu, durasi pinjaman, masa angsuran, tenor pinjaman | Multifinance | Universally borrowed financial term for loan duration |
| **ID** | `penalty` | denda, biaya keterlambatan, late fee, pinalti | Multifinance | "Denda" is standard; "late fee" used in credit card contexts |
| **ID** | `down_payment` | DP, uang muka, panjar, down payment, setoran awal | Multifinance | Spoken almost universally as "D-P" in automotive/leasing |
| **ID** | `due_date` | jatuh tempo, tanggal tagihan, batas pembayaran, due date | Multifinance | Essential reminder terminology for collection prevention |
| **ID** | `financing` | pembiayaan, kredit, pinjaman multifinance, dana tunai | Multifinance | Regulatory OJK term is "pembiayaan"; consumers say "kredit" |

---

## 7. ASR Provider & Model Configuration

### Documented Provider Architecture
- **Provider**: **Deepgram Nova 3** via Vapi Multilingual Assistant Configuration.
- **Vapi Transcriber Config**:
  ```json
  {
    "provider": "deepgram",
    "model": "nova-3",
    "language": "multi"
  }
  ```
- **Language Coverage**: Deepgram lists both Indonesian (`id`) and Tagalog (`tl`) in multilingual Nova 3.
- **Development Fallback**: In environments without live audio stream or Vapi credentials, `HeuristicLanguageDetector` (`backend/app/localization/language.py`) provides rule-based token analysis, register classification, and code-switch detection.

---

## 8. TTS Provider & Model Configuration

### Documented Voice Architecture
- **Provider**: **ElevenLabs Multilingual v2** via Vapi Voice Configuration.
- **Provider Config Parameters**:
  - Model: `eleven_multilingual_v2`
  - Latency Target: P95 < 650 ms (`optimize_streaming_latency=3`)
  - Voice ID Presets:
    - Philippines: `elevenlabs:ph_filipino_female_01` (Natural Tagalog/Taglish accent)
    - Indonesia: `elevenlabs:id_indonesian_male_01` (Neutral Bahasa Indonesia)
- **Fallback Voice Config**: Vapi standard neural voices (`neets`, `playht`, or OpenAI TTS-1 `alloy`/`shimmer`) configured as secondary redundancy.

---

## 9. Regional Accent Test Design (`data/eval/q3_asr/indonesia_regional.json`)

Standard speech recognition often fails outside metropolitan Jakarta (Betawi/Jaksel slang). To rigorously evaluate non-metropolitan comprehension without fabricating live benchmark numbers, we established an explicit regional test suite.

### Evaluated Regional Accents
1. **East Java / Surabaya (`jawa_timur_surabayan`)**:
   - Distinctive phonological markers: Heavy retroflex consonants (`b`, `d`), glottal stops, and lexical markers (`rek`, `tah`, `sak durunge`).
   - Test Utterance: *"Iki lho rek, cicilan sepeda motore opo isok dowo tenore telung tahun? Ojo sampek kenek denda lek telat yo."*
   - Expected Canonical Mapping: `cicilan` -> `installment`, `tenor` -> `tenor`, `denda` -> `penalty`.
2. **West Java / Sundanese (`jawa_barat_sundanese`)**:
   - Phonological tendency: `f`/`p` sound shifts, polite softening particles (`teh`, `mah`, `atuh`).
   - Test Utterance: *"Punten teh, abdi bade naroskeun perkawis DP mobil sareng angsuran bulanan, tiasa kirang teu denda pami telat bayar?"*
   - Expected Canonical Mapping: `DP` -> `down_payment`, `angsuran` -> `installment`, `denda` -> `penalty`.
3. **North Sumatra / Medan (`sumatera_utara_medan`)**:
   - Sharp cadence, distinct questioning intonation, direct terminology (`lah`, `kali`, `tengok`).
   - Test Utterance: *"Halo Bos, cemana ini rincian cicilan kredit ku? Jatuh tempo nya kapan rupanya, jangan mendadak kali dendanya."*
   - Expected Canonical Mapping: `cicilan` -> `installment`, `jatuh tempo` -> `due_date`, `denda` -> `penalty`.

*Status: Clearly marked `TEST CASE PREPARED — AUDIO NOT YET AVAILABLE`. No synthetic acoustic scores are fabricated.*

---

## 10. Localized Fallback Policy (`backend/app/localization/fallback.py`)

A critical failure mode of voice bots is reverting to English when an ungrounded question, ASR dropout, or internal failure occurs during a localized conversation.

### Guarantees
1. **Language & Register Preservation**: If caller speaks Taglish or Tagalog, fallback response remains strictly in Tagalog/Taglish. If caller speaks Indonesian, fallback matches caller register (`id_formal` or `id_colloquial`).
2. **Fallback Triggers Covered**:
   - `UNSUPPORTED_KB_QUESTION`: Caller asks an ungrounded or out-of-scope question.
   - `LOW_CONFIDENCE_ASR`: Speech recognition clarity score falls below threshold.
   - `TOOL_FAILURE`: Webhook or lead creation error.
   - `UNCLEAR_STATEMENT`: Caller utterance is garbled or ambiguous.
   - `HUMAN_ESCALATION`: Caller requests a representative.

### Fallback Examples

| Market | Condition | Natural Localized Output |
|--------|-----------|--------------------------|
| **PH (Taglish)** | Unsupported KB | *"Pasensya na po, wala po sa aking verified bancassurance records ang impormasyong iyan. Para po masigurado, pwede ko po kayong i-connect sa ating senior policy specialist."* |
| **PH (Taglish)** | Low Confidence ASR | *"Pasensya na po, medyo naputol po ang inyong linya. Pwede po bang pakiulit ang inyong katanungan tungkol sa inyong policy?"* |
| **ID (Formal)** | Unsupported KB | *"Mohon maaf, informasi detail mengenai hal tersebut belum tercatat dalam sistem resmi multifinance kami. Agar lebih jelas, saya dapat menyambungkan Anda dengan petugas pembiayaan kami."* |
| **ID (Colloquial)** | Low Confidence ASR | *"Halo Kak, suaranya tadi agak terputus. Boleh tolong diulang pertanyaannya soal cicilan tadi?"* |

---

## 11. Localization Examples (>= 3 per Market)

### Philippines (Bancassurance)

#### Example 1: Payment Grace Period & Anti-Lapse Clarification
- **English / Base Intent**: *"What happens if I cannot pay my premium on time this month?"*
- **Localized Wording**: *"Naiintindihan ko po ang inyong pag-aalala. Sa ilalim po ng ating bancassurance guidelines, mayroon po kayong 31 days grace period mula sa due date. Ibig sabihin po, active pa rin ang inyong coverage at hindi agad magla-lapse ang inyong policy habang nag-aayos kayo ng payment."*
- **Why It Is Localized**: Reassures the customer with empathetic consultative tone (`Naiintindihan ko po...`) rather than sterile contractual warning. Uses standard Taglish loanwords (`due date`, `grace period`, `coverage`, `policy`, `lapse`).
- **Terminology / Cultural Consideration**: Retains respectful markers (`po`), avoids confusing formal Tagalog translations of technical insurance concepts, and reduces financial anxiety.

#### Example 2: Medical Rider & Additional Protection Inquiry
- **English / Base Intent**: *"Is critical illness covered under this life insurance plan?"*
- **Localized Wording**: *"Magandang tanong po! Ang inyong basic life plan po ay pwedeng lagyan ng critical illness rider para po kung magkaroon ng malubhang karamdaman, may lump sum cash benefit kayong matatanggap na bukod pa sa regular hospitalization allowance."*
- **Why It Is Localized**: Clarifies the structural difference between a base plan and an add-on ("rider") using everyday conversational phrasing (*"lagyan ng dagdag na rider"*).
- **Terminology / Cultural Consideration**: In Philippine bancassurance, riders are sold as family financial shields. Using *"lump sum cash benefit"* and *"hospitalization allowance"* matches bank teller explanations.

#### Example 3: Branch Endorsement & Direct Bank Specialist Escalation
- **English / Base Intent**: *"I want to talk to an agent at the bank branch."*
- **Localized Wording**: *"Walang problema po! I-forward ko po agad ang inyong inquiry sa ating bancassurance specialist sa pinakamalapit ninyong bangko para matawagan po kayo at ma-review ang inyong mga dokumento nang personal."*
- **Why It Is Localized**: Validates the customer's preference for in-person branch relationships (*"bancassurance specialist sa bangko"*) rather than a detached call center transfer.
- **Terminology / Cultural Consideration**: Filipino consumers have high trust in physical bank branches (*"sa pinakamalapit ninyong bangko"*). The bot positions the escalation as a helpful bank endorsement.

---

### Indonesia (Multifinance)

#### Example 1: Vehicle Installment & Down Payment (DP) Inquiry
- **English / Base Intent**: *"How much is the monthly payment if I pay a 20% down payment?"*
- **Localized Wording (Formal)**: *"Baik Bapak/Ibu, untuk simulasi pembiayaan kendaraan dengan uang muka atau DP 20%, kami dapat menyesuaikan tenor mulai dari 12 hingga 48 bulan agar nilai cicilan bulanan tetap terjangkau dan sesuai kemampuan keuangan Anda."*
- **Localized Wording (Colloquial)**: *"Oke Kak, kalau DP 20%, cicilannya bisa kita atur tenornya mau 1 sampai 4 tahun biar angsuran per bulannya enteng dan nggak berat di kantong!"*
- **Why It Is Localized**: Directly deploys standard retail terminology (`DP`, `angsuran`, `cicilan`, `tenor`) with distinct formal (`Bapak/Ibu`) versus casual app-based fintech register (`Kak`, `nggak berat di kantong`).
- **Terminology / Cultural Consideration**: "Uang muka" is formally paired with the spoken abbreviation "DP". The conversational register uses popular financial idioms ("enteng di kantong" = light on the wallet).

#### Example 2: Grace Period & Late Penalty (Denda) Objection
- **English / Base Intent**: *"Why are you charging me a penalty fee when I only paid two days late?"*
- **Localized Wording (Formal)**: *"Kami memahami kendala yang Bapak/Ibu hadapi. Berdasarkan ketentuan pembiayaan, denda keterlambatan mulai dihitung secara otomatis setelah melewati tanggal jatuh tempo. Namun, jika ada kendala darurat, mari kami bantu periksa catatan transaksi Anda di sistem."*
- **Why It Is Localized**: Defuses confrontation through respectful acknowledgment (*"Kami memahami kendala yang Bapak/Ibu hadapi"*) without conceding contractual terms.
- **Terminology / Cultural Consideration**: In Indonesian debt collection culture, aggressive statements cause borrowers to disengage. Soft formal language preserves customer dignity while explaining system automation.

#### Example 3: Restructuring & Branch Collector Escalation
- **English / Base Intent**: *"I lost my job and cannot pay this amount anymore. Let me speak to your manager."*
- **Localized Wording (Formal)**: *"Kami turut prihatin atas situasi yang dialami Bapak/Ibu. Segera saya sambungkan dengan tim restrukturisasi pembiayaan kami agar Bapak/Ibu dapat mendiskusikan keringanan cicilan atau perpanjangan tenor bersama petugas kami secara langsung."*
- **Why It Is Localized**: Focuses immediately on loan restructuring (*"restrukturisasi pembiayaan"*) and installment relief (*"keringanan cicilan"*), which are standard OJK-regulated consumer protections.
- **Terminology / Cultural Consideration**: Directly transfers to the specialized loan modification officer rather than a generic call center supervisor.

---

## 12. Evaluation Results & Manifests

### Automated Evaluation Summary
All 30 unit and integration tests pass successfully in `backend/tests/`:
- `test_localization.py` (5 tests)
- `test_terminology.py` (5 tests)
- `test_language_detection.py` (5 tests)
- `test_fallback_localized.py` (5 tests)
- `test_market_configs.py` (5 tests)
- `test_q3_retrieval.py` (5 tests)

### ASR Test Suite (`data/eval/q3_asr/`)
- **Philippines Manifest (`philippines.json`)**: 10 categorized utterances testing normal speech, numbers, dates, insurance terms (`grace period`, `lapsed policy`), objections, and human escalation.
- **Indonesia Manifest (`indonesia.json`)**: 10 categorized utterances testing formal/colloquial speech, loanwords, currency numbers (`dua juta lima ratus ribu rupiah`), loan duration dates, and penalty fees (`denda`).
- **Regional Manifest (`indonesia_regional.json`)**: 3 regional accent cases (Surabaya, Sundanese, Medan) with exact phonetic transcripts and canonical concept mappings.

*Status: Audio files are currently not present. Manifests are verified and recorded as `NOT RUN — AUDIO NOT AVAILABLE` and `TEST CASE PREPARED — AUDIO NOT YET AVAILABLE`.*

---

## 13. Known Limitations & Next Steps

1. **Simulation vs Live Vapi Audio**:
   - Call evidence files (`evidence/q3/philippines/call-01.json`, etc.) represent full multi-turn conversational simulations validating state transitions, localized terminology, and Q2 retrieval.
   - Live Vapi audio recordings over telephone or WebRTC have not yet been captured due to absent external telephony credentials. They are accurately marked `SIMULATION — NOT LIVE CALL`.
2. **Text Heuristic Language Detector**:
   - `backend/app/localization/language.py` operates on written/transcribed tokens. In live deployment, primary language identification should be delegated to Deepgram Nova 3's real-time streaming language classification.
3. **Regional Accent Acoustic Benchmark**:
   - The regional test suite defines phonetic and lexical structures for Surabaya, Sundanese, and Medan dialects, but empirical Word Error Rate (WER) requires field-recorded acoustic files.
