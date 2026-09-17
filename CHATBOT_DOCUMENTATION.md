# Schemora AI Chatbot — Full Technical Documentation

## Table of Contents
1. [System Architecture Overview](#1-system-architecture-overview)
2. [Text Chatbot Pipeline](#2-text-chatbot-pipeline)
3. [Voice Assistant Pipeline](#3-voice-assistant-pipeline)
4. [Multilingual Support](#4-multilingual-support)
5. [Knowledge Base & RAG Architecture](#5-knowledge-base--rag-architecture)
6. [Backend Setup & Configuration](#6-backend-setup--configuration)
7. [Frontend Setup](#7-frontend-setup)
8. [API Reference](#8-api-reference)
9. [Acceptance Test Results](#9-acceptance-test-results)
10. [Known Issues & Workarounds](#10-known-issues--workarounds)

---

## 1. System Architecture Overview

```
┌──────────────────────────────┐     HTTP (REST, JSON)
│  Flutter Frontend (Android)  │ ────────────────────────────────►
│  - AssistantChatScreen       │                                 │
│  - VoiceAssistantService     │                                 │
│  - AIRepositoryImpl          │                                 │
└──────────────────────────────┘                                 │
                                                                  ▼
                                              ┌───────────────────────────────┐
                                              │  FastAPI Backend (Python)     │
                                              │  - /api/v1/ai/chat            │
                                              │  - /api/v1/ai/speech-to-text  │
                                              │  - /api/v1/ai/text-to-speech  │
                                              └──────────────┬────────────────┘
                                                             │
                              ┌──────────────────────────────┼────────────────────────────┐
                              ▼                              ▼                            ▼
                  ┌──────────────────┐          ┌────────────────────┐       ┌────────────────────┐
                  │  Query           │          │  pgvector /        │       │  Groq LLM API      │
                  │  Understanding   │          │  SQLite Knowledge  │       │  (llama-3.3-70b +  │
                  │  Service         │          │  Base              │       │  Whisper v3)       │
                  └──────────────────┘          └────────────────────┘       └────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | Flutter 3.x (Dart) with Riverpod state management |
| Backend | FastAPI (Python 3.12) with Uvicorn ASGI server |
| Database | SQLite (dev) / PostgreSQL (prod) with pgvector extension |
| Embeddings | TF-IDF (dev) / sentence-transformers (prod) |
| LLM | Groq API — `llama-3.3-70b-versatile` model |
| STT | Device-native `speech_to_text` (live preview) + Groq API `whisper-large-v3` (final transcript and spoken-language detection); audio captured with `record` |
| TTS | Device-native `flutter_tts` (the only engine the app uses) |
| Server TTS (unused by app) | `POST /ai/text-to-speech` proxies Google Translate's unofficial `translate_tts` endpoint — undocumented, rate-limited, not for production |
| HTTP Client | Dio (Flutter) / httpx (Python async) |

### External APIs and Services

| Service | Used for | Required? |
|---------|----------|-----------|
| Groq Chat Completions (`llama-3.3-70b-versatile`, falls back to `llama-3.1-8b-instant`, `llama3-8b-8192`) | Writing the final answer from retrieved context | Optional — without it a verified-KB summary is returned |
| Groq Audio Transcriptions (`whisper-large-v3`) | Voice transcription + language detection | Required for voice language auto-detection |
| Android/iOS speech recognizer (`speech_to_text`) | Live transcript while speaking; fallback if Whisper fails | Device-dependent |
| Android/iOS TTS engine (`flutter_tts`) | Reading answers aloud | Device needs voice packs per language |
| PostgreSQL + pgvector / SQLite | Knowledge base storage and vector search | Required |

> `web_search_service.py` exists but is **not wired** into `/ai/chat`; `web_search_used` in the response is always `false` today.

---

## 2. Text Chatbot Pipeline

### Complete Request Flow

```
[User Types/Speaks Query]
        ↓
[Frontend: AssistantChatScreen._sendMessage()]
        ↓ POST /api/v1/ai/chat
[Backend: chat_assistant()]
        ↓
[Intent Detection: detect_intent()]
 • GREETING → direct response (no retrieval)
 • THANKS    → direct response (no retrieval)
 • GOODBYE   → direct response (no retrieval)
 • UNKNOWN   → clarification message
 • AMBIGUOUS → disambiguation message
 • SCHEME_DISCOVERY / SPECIFIC_SCHEME / ELIGIBILITY / etc.
        ↓
[Entity Extraction: extract_query_entity_and_section()]
 • Extracts: scheme name, portal name, section type
 • Typo-tolerant via FuzzyMatcher (Levenshtein distance)
        ↓
[RAG Retrieval: retrieve_relevant_chunks()]
 • Query expansion based on intent
 • Embedding (TF-IDF or dense)
 • pgvector similarity search
 • Section-affinity boost by intent
 • Keyword matching boost
 • Entity-specific filtering
        ↓
[Relevance gate: evaluate_chunk_relevance()]
 • Discards retrieved chunks that neither score ≥ 0.045 nor share a keyword with the query
 • Discarded → "couldn't find verified information" reply instead of a guess
        ↓
[Groq LLM Response: generate_grounded_chat_response()]
 • Context-grounded prompt construction
 • Language-specific instructions
 • Strict: answer only from retrieved context
 • If Groq is unconfigured / times out (6 s per model): verified-KB summary card
   with localized labels; non-English users get a notice that details are in English
        ↓
[Citation Building: _build_citations()]
 • Per-scheme official URLs
 • No generic india.gov.in fallbacks
        ↓
[Response Formatting & Return to Frontend]
```

### Intent Types Supported

| Intent | Description | Example Query |
|--------|-------------|---------------|
| `GREETING` | Welcome/introduction | "hello", "hi", "namaste" |
| `THANKS` | Thank you messages | "thanks", "thank you" |
| `GOODBYE` | Farewell | "bye", "goodbye" |
| `DEFINITION_CONCEPT` | Term definitions | "What is a government scheme?" |
| `SCHEME_DISCOVERY` | Finding schemes | "Schemes for farmers in Maharashtra" |
| `SPECIFIC_SCHEME` | Scheme details | "Tell me about PM-KISAN" |
| `ELIGIBILITY` | Who can apply | "Am I eligible for PM-KISAN?" |
| `REQUIRED_DOCUMENTS` | Document checklist | "Documents for PM-KISAN" |
| `APPLICATION_PROCESS` | How to apply | "How do I apply for MYSY?" |
| `BENEFITS` | Financial benefits | "What is the PM-KISAN amount?" |
| `CONTACT` | Helpline/contact info | "PM-KISAN helpline number" |
| `COMPARISON` | Compare schemes | "Compare PM-KISAN vs PMFBY" |
| `PORTAL_INFO` | Portal details | "What is MahaDBT?" |
| `PORTAL_APPLICATION` | Apply via portal | "How do I apply on NSP?" |
| `AMBIGUOUS` | Multiple matches | "Tell me about PM scheme" |
| `UNKNOWN` | Unrecognized query | "xyzabc" |

### Handling Uncertainty

| Situation | Response | `is_grounded` |
|-----------|----------|---------------|
| Answer generated from retrieved KB context | Answer + per-scheme citations | `true` |
| Nothing relevant retrieved | "I couldn't find verified information…" + official-portal pointer | `false` |
| Specific question without a scheme name | Asks which scheme | `false` |
| Ambiguous / unrecognized query | Asks the user to clarify | `false` |
| Out-of-scope topic (weather, cricket…) | Scope refusal | `false` |
| Greeting / thanks / goodbye | Canned reply | `true` |
| Portal question (MahaDBT, NSP, myScheme, Jan Samarth) | That portal's own description / apply steps + official URL | `true` |

---

## 3. Voice Assistant Pipeline

### Complete Voice Flow

```
[User Taps Microphone Button]
        ↓
[VoiceAssistantService.startListening()]
 • `record` captures raw audio (m4a) in parallel
 • SpeechToText.listen() in the currently selected locale → live preview text
   (Android Emulator: requires Google Speech Services)
        ↓
[User taps Done → VoiceAssistantService.stopListening()]
        ↓
[POST /ai/speech-to-text — Groq Whisper, NO language hint]
 • Whisper detects the spoken language from the audio itself
 • Backend maps Whisper's language name (e.g. "marathi") → ISO code
 • Whisper transcript replaces the preview; language selector switches to the
   detected language (onLanguageDetected)
 • If Whisper fails, the device transcript is kept
        ↓
[AssistantChatScreen._sendMessage(wasAskedViaVoice: true)]
        ↓
[Same text chatbot pipeline as above...]
        ↓
[TTS Playback: VoiceAssistantService.speak()]
 • flutter_tts reads the answer using the `language` field returned by /ai/chat
   (the language the answer was actually written in)
```

**Limitation:** the live preview uses the device recognizer, which needs a locale up front, so the preview may be wrong until Whisper returns. Whisper is what makes "reply in the language you spoke" work — without `GROQ_API_KEY` voice only works in the pre-selected language.

### Voice Permissions (AndroidManifest.xml)

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.INTERNET"/>
```

### Voice Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "Listening…" stuck | STT engine unavailable | Tap "Done" to manually stop; ensure Google app installed |
| "Microphone permission required" | RECORD_AUDIO denied | Grant in Settings > Apps > Schemora |
| Empty transcription | Background noise / accent | Speak clearly, use text fallback |
| Connection error | Backend unreachable | Check emulator network `10.0.2.2:8000` |

### Backend URL Selection

`EnvConfig.baseUrl` (`lib/core/config/env_config.dart`) picks one URL — there is no multi-host retry:
1. `--dart-define=API_BASE_URL=...` if provided
2. Android: `http://10.0.2.2:8000/api/v1/` (emulator → host machine)
3. Web / desktop: `http://127.0.0.1:8000/api/v1/`

For a physical device, pass `API_BASE_URL` with your machine's LAN IP.

---

## 4. Multilingual Support

### Supported Languages

| Language | Code | Script | STT | TTS | Chat |
|----------|------|--------|-----|-----|------|
| English | `en` | Latin | ✅ | ✅ | ✅ |
| Hindi | `hi` | Devanagari | ✅ | ✅ | ✅ |
| Gujarati | `gu` | Gujarati | ✅ | ✅ | ✅ |
| Marathi | `mr` | Devanagari | ✅ | ✅ | ✅ |
| Bengali | `bn` | Bengali | ✅ | ✅ | ✅ |
| Tamil | `ta` | Tamil | ✅ | ✅ | ✅ |
| Telugu | `te` | Telugu | ✅ | ✅ | ✅ |
| Kannada | `kn` | Kannada | ✅ | ✅ | ✅ |
| Malayalam | `ml` | Malayalam | ✅ | ✅ | ✅ |
| Punjabi | `pa` | Gurmukhi | ✅ | ✅ | ✅ |

### Language Detection

The language the user *writes or speaks in* wins; the app's selected language is only a hint.

**Frontend** (`_detectLanguageFromText` / `_resolveLanguage`): Unicode script ranges. Devanagari is Marathi if it contains Marathi-only words (आहे, नाही, मला…), otherwise Hindi — unless Marathi is already selected. Latin text keeps the current selection.  
**Backend** (`language_service.detect_language(text, hint)`):
1. Native script → that language (Devanagari: Marathi markers or `hint=mr` → Marathi, else Hindi)
2. Latin text + hint `hi`/`gu`/`mr` + romanized markers of that language (e.g. *kya, hai, liye* / *che, shu, mate* / *aahe, mala, sathi*) → hint language
3. Other Latin text → English  
**Voice**: Whisper's detected spoken language (see §3).  
**LLM Prompt**: Explicit instruction to respond ONLY in the detected language — no mixing.  
**Response**: `/ai/chat` returns `language`, which the app uses for TTS.

### Language Response Flow

```
[User sends Hindi query: "पीएम किसान क्या है?"]
        ↓
[Frontend detects Devanagari script → lang = 'hi']
        ↓ POST /api/v1/ai/chat {question: "...", language: "hi"}
[Backend: language_service.detect_language() → hi]
        ↓
[translate_query_for_retrieval(): Indic keywords → English domain terms
 (Hindi, Marathi, Gujarati, Bengali, Tamil, Telugu, Kannada, Malayalam, Punjabi,
  plus common romanized words)]
        ↓
[pgvector retrieval using the expanded query]
        ↓
[Groq prompt: "CRITICAL: Respond STRICTLY AND ONLY IN HINDI (हिंदी)"]
        ↓
[Hindi response returned with "language": "hi"]
```

**Limitation:** the knowledge base is English. Non-English answers depend on Groq translating the context; if Groq is unavailable the fallback card shows English details with localized labels and a notice.

---

## 5. Knowledge Base & RAG Architecture

### Chunk Structure

Each scheme in the knowledge base is split into up to 16 section-level chunks:

| Section | Content |
|---------|---------|
| `overview` | Scheme name, description, department, category |
| `benefits` | Financial aid amounts, coverage, frequency |
| `eligibility` | Who can apply, criteria, conditions |
| `documents` | Required documents checklist |
| `application` | Step-by-step application process |
| `deadlines` | Application windows, dates |
| `notes` | Verification status, caveats |
| `faqs` | Frequently asked questions |
| `objective` | Scheme purpose |
| `financial_details` | Specific amounts, currency, frequency |
| `beneficiaries` | Target demographic groups |
| `application_channels` | Online portal URL, offline CSC |
| `status` | Active/Closed/Upcoming |
| `renewal` | Renewal criteria and process |
| `restrictions` | Exclusions, who cannot apply |
| `contact` | Helpline, email, grievance portal |

### Retrieval Strategy

1. **Query Expansion**: Add intent-specific terms (e.g., for `ELIGIBILITY` → "eligible eligibility criteria who can apply")
2. **Dense Embedding**: sentence-transformers (when available) or TF-IDF fallback
3. **pgvector Cosine Similarity**: Vector search over all chunks
4. **Section Boost**: +0.25–0.50 to chunks matching the detected intent
5. **Keyword Boost**: +0.15 per matching query keyword in scheme name/category
6. **Demographic Boost**: +0.45 for gender/occupation/category matches (farmer, women, etc.)
7. **Entity Filtering**: If entity detected, filter to entity-matched chunks only
8. **Deduplication**: 1 chunk per scheme for `SCHEME_DISCOVERY`, multiple sections allowed for specific queries

### Glossary Service

For `DEFINITION_CONCEPT` queries, a special glossary of government scheme terms is maintained:
- Terms: scheme, eligibility, beneficiary, subsidy, DBT, CSC, scholarship, etc.
- Each term has: Definition, Purpose, Hindi Explanation, Gujarati Explanation
- Retrieved before any vector search for definition queries

---

## 6. Backend Setup & Configuration

### Prerequisites

- Python 3.11+
- `uv` package manager (or `pip`)

### Installation

```powershell
cd backend
uv sync
```

### Environment Variables (`.env`)

```env
PROJECT_NAME="Schemora API"
API_V1_STR="/api/v1"
APP_ENV="development"
DATABASE_URL="sqlite+aiosqlite:///./schemora_dev.db"
GROQ_API_KEY=<your_groq_api_key>
GROQ_GENERATION_MODEL="llama-3.3-70b-versatile"
HOST="0.0.0.0"
PORT=8000
```

> ⚠️ **Security**: Never commit `GROQ_API_KEY` to version control. Add `.env` to `.gitignore`.

### Running the Backend

```powershell
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Database Initialization

```powershell
# Apply migrations
uv run alembic upgrade head

# Index knowledge base from schemes.v1.json
# POST /api/v1/ai/knowledge-base/index (via HTTP) OR:
uv run python scripts/run_kb_indexing.py
```

### Knowledge Base Dataset Location

```
data/schemes/schemes.v1.json      (primary)
backend/data/final/schemes.json   (fallback)
```

---

## 7. Frontend Setup

### Prerequisites

- Flutter SDK 3.x
- Android Studio with Android Emulator (API 30+)

### Installation

```powershell
cd frontend
flutter pub get
```

### Running on Android Emulator

```powershell
flutter run -d <emulator_device_id>
```

### API Base URL Configuration

Computed by `EnvConfig.baseUrl` in `lib/core/config/env_config.dart` (see §3 "Backend URL Selection"). Override it at build time:
```powershell
flutter run --dart-define=API_BASE_URL=http://<your-lan-ip>:8000/api/v1/
```

### Microphone Permission Handling

The `VoiceAssistantService.initSpeech()` automatically handles permission requests via the `speech_to_text` plugin. No manual permission flow is needed.

---

## 8. API Reference

### POST `/api/v1/ai/chat`

Chat with the AI assistant.

**Request Body:**
```json
{
  "question": "What is PM-KISAN?",
  "language": "en",
  "scheme_id": null,
  "state_filter": null,
  "category_filter": null,
  "conversation_context": {"last_scheme": "PM-KISAN", "last_intent": "SPECIFIC_SCHEME"}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "answer": "PM-KISAN is a Central Government scheme...",
    "is_grounded": true,
    "language": "en",
    "citations": [{"source_name": "...", "url": "...", "last_verified_at": "..."}],
    "retrieved_schemes": [...],
    "confidence_score": 0.85,
    "suggested_questions": ["..."],
    "conversation_context": {"last_scheme": "PM-KISAN", "last_intent": "SPECIFIC_SCHEME"}
  }
}
```

### POST `/api/v1/ai/speech-to-text`

Transcribe audio to text (multipart form).

**Form fields:**
- `file`: Audio file (WAV, MP3, M4A, WebM)
- `language`: Optional ISO language code. **Omit it** to let Whisper detect the spoken language (the app omits it).

`language` in the response is the detected ISO code (Whisper's detection when it names a supported language, otherwise script detection on the transcript); `raw_language` is Whisper's raw label.

**Response:**
```json
{
  "success": true,
  "data": {
    "text": "What is PM KISAN?",
    "language": "en",
    "raw_language": "english"
  }
}
```

### POST `/api/v1/ai/text-to-speech`

Generate speech audio from text.

**Request Body:**
```json
{"text": "Hello! I am your Schemora AI assistant.", "language": "en"}
```

**Response:** Raw MP3 audio bytes (`audio/mpeg`)

> Uses Google Translate's unofficial `translate_tts` endpoint. The Flutter app does **not** call this endpoint (it uses on-device `flutter_tts`); treat it as a dev/testing utility.

### GET `/api/v1/ai/knowledge-base/status`

Get knowledge base statistics.

### POST `/api/v1/ai/knowledge-base/index`

Trigger full re-indexing of schemes dataset.

---

## 9. Acceptance Test Checklist

These are the acceptance checks for each requirement. Record the result and date when you run them — a row is only "passed" once it has been run against the current code. Items marked *(changed 2026-09-17)* cover behaviour changed in the latest fix round and have **not been re-run yet**.

### Requirement 1: Search via Chatbot

| # | Test Query | Expected Behavior |
|---|-----------|-------------------|
| 1 | "hello" | Greeting response (no scheme clarification) |
| 2 | "hi" | Greeting response |
| 3 | "What is a government scheme?" | Definition response |
| 4 | "Tell me about PM-KISAN" | PM-KISAN scheme overview |
| 5 | "Documents for PM-KISAN" | Document checklist |
| 6 | "How to apply for PM-KISAN" | Step-by-step process |
| 7 | "Schemes for farmers in Maharashtra" | List of farmer schemes |
| 8 | "Scholarships for students" | List of scholarships |
| 9 | "Compare PM-KISAN vs PM Internship" | Comparison table |
| 10 | "What are the eligibilty criteria for PM-KISAN?" (typo) | Correct eligibility info |
| 11 | "xyzabc" | "I'm not sure what you mean" |
| 12 | Scheme name present but KB returns nothing *(changed)* | DB fallback answer, not the generic error message |

### Requirement 2: Voice Support

| # | Test | Expected |
|---|------|----------|
| 1 | Tap mic button | "Listening..." UI shown |
| 2 | Speak "hello" | Text appears in input field |
| 3 | Tap Done | Query sent to chatbot |
| 4 | Bot responds | TTS plays response audio |
| 5 | Error handling | Clear error SnackBar shown |
| 6 | App set to English, speak Gujarati *(changed)* | Transcript in Gujarati, language chip switches to Gujarati, answer spoken in Gujarati |
| 7 | App set to Hindi, type an English question *(changed)* | English answer read with an English voice |

### Requirement 3: Multilingual

| # | Query | App language | Expected Response Language |
|---|-------|--------------|--------------------------|
| 1 | "पीएम किसान क्या है?" | any | Hindi |
| 2 | "PM Kisan ke liye kya documents chahiye?" *(changed)* | hi | Hindi |
| 3 | "PM Kisan mate kya documents joie?" *(changed)* | gu | Gujarati |
| 4 | "PM Kisan documents?" | gu | English (no Gujarati markers) |
| 5 | "मला पीएम किसान योजनेची माहिती हवी आहे" *(changed)* | en | Marathi |
| 6 | "hello" | en | English greeting |
| 7 | Hindi question with `GROQ_API_KEY` unset *(changed)* | hi | Hindi notice + Hindi labels, details in English |

### Requirement 4: Accurate Answers

| # | Test | Expected |
|---|------|----------|
| 1 | PM-KISAN response contains correct ₹6000 amount | From verified KB |
| 2 | Citations contain scheme-specific URLs | No india.gov.in generic links |
| 3 | Greeting doesn't return scheme clarification | Intent detection accurate |
| 4 | Typo tolerance ("eligibilty" → ELIGIBILITY intent) | Fuzzy matching works |
| 5 | "Tell me about NSP scholarship" *(changed)* | Describes the Government of India portal — no mention of Maharashtra |
| 6 | Query with only weakly-related KB matches *(changed)* | "Couldn't find verified information", `is_grounded: false` |
| 7 | "How do I apply?" (no scheme) *(changed)* | Asks for scheme name, `is_grounded: false` |

### Requirement 5: Documentation

This document, including the tools/APIs table in §1.

---

## 10. Known Issues & Workarounds

### Voice on Android Emulator

**Issue**: Android emulators may not have Google Speech Services installed, causing `speech_to_text` to fail.

**Workaround**: 
1. Open the emulator's Play Store and install/update "Google" app
2. Or use a physical Android device for voice testing
3. As a fallback, text input always works

### TTS on Android Emulator

**Issue**: `flutter_tts` requires an installed TTS engine. Some emulators may lack Hindi/Gujarati voices.

**Workaround**: 
1. Install Google Text-to-Speech in emulator Play Store
2. Go to Settings > Accessibility > Text-to-speech and download language packs

### Network Connectivity (Emulator)

**Issue**: `localhost` doesn't work inside Android emulator; must use `10.0.2.2`.

**Workaround**: `EnvConfig.baseUrl` uses `10.0.2.2` on Android automatically. On a physical device, pass `--dart-define=API_BASE_URL=http://<lan-ip>:8000/api/v1/`.

### Voice Language Detection Needs Groq

**Issue**: Only Whisper can detect the spoken language. Without `GROQ_API_KEY` (or if the call fails), the device recognizer's transcript in the pre-selected locale is used.

**Workaround**: Configure `GROQ_API_KEY`, or select the language in the app before speaking.

### Groq Timeout → English Details

**Issue**: Groq calls time out after 6 s per model. When all models fail, non-English users get the KB summary in English (with localized labels and a notice), because the knowledge base is English-only.

### Knowledge Base (Development)

**Issue**: Development mode uses SQLite + TF-IDF embeddings (not pgvector).

**Impact**: Retrieval quality is lower than production (pgvector + dense embeddings).

**Fix**: Run PostgreSQL with pgvector extension for production-grade retrieval.

### Groq API Rate Limits

**Issue**: Groq free tier has rate limits (30 requests/minute on llama-3.3-70b).

**Workaround**: The backend has a model fallback chain: `llama-3.3-70b-versatile` → `llama-3.1-8b-instant` → `llama3-8b-8192`.

---

*Documentation version: 1.1 — Last updated: 2026-09-17*
