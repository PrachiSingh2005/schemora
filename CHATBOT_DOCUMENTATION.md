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
┌──────────────────────────────┐     HTTP / WebSocket
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
| STT | Groq API — `whisper-large-v3` model |
| TTS | Device-native `flutter_tts` (primary) / Google Translate TTS (fallback) |
| HTTP Client | Dio (Flutter) / httpx (Python async) |

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
[Groq LLM Response: generate_grounded_chat_response()]
 • Context-grounded prompt construction
 • Language-specific instructions
 • Strict: answer only from retrieved context
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

---

## 3. Voice Assistant Pipeline

### Complete Voice Flow

```
[User Taps Microphone Button]
        ↓
[VoiceAssistantService.startListening()]
        ↓
[SpeechToText.listen() — device STT engine]
 • Android Emulator: requires Google Speech Services
 • Language detection automatic from typed script
        ↓
[onResult callback — partial results shown in text field]
        ↓
[onDone callback — fires when speech ends]
        ↓
[AssistantChatScreen._sendMessage(wasAskedViaVoice: true)]
        ↓
[Same text chatbot pipeline as above...]
        ↓
[TTS Playback: VoiceAssistantService.speak()]
 • flutter_tts plays bot response
 • Language auto-detected from response
```

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

### Network Fallback (Android Emulator)

The `AIRepositoryImpl` tries these hosts in order:
1. Configured Dio base URL (from `api_client.dart`)
2. `10.0.2.2:8000` (standard Android emulator localhost)
3. `127.0.0.1:8000`
4. `10.59.33.142:8000` (LAN IP fallback)

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

**Frontend**: Automatic script detection from Unicode block ranges  
**Backend**: `language_service.py` uses regex patterns for each script  
**LLM Prompt**: Explicit instruction to respond ONLY in detected language — no mixing

### Language Response Flow

```
[User sends Hindi query: "पीएम किसान क्या है?"]
        ↓
[Frontend detects Devanagari script → lang = 'hi']
        ↓ POST /api/v1/ai/chat {question: "...", language: "hi"}
[Backend: language_service.detect_language() → hi]
        ↓
[Query Understanding: translate_query_for_retrieval() for English retrieval]
        ↓
[pgvector retrieval using English translation]
        ↓
[Groq prompt: "CRITICAL: Respond STRICTLY AND ONLY IN HINDI (हिंदी)"]
        ↓
[Hindi response returned, no English mixing]
```

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
cd d:\Schemora\backend
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
cd d:\Schemora\backend
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
d:\Schemora\data\schemes\schemes.v1.json   (primary)
d:\Schemora\backend\data\final\schemes.json (fallback)
```

---

## 7. Frontend Setup

### Prerequisites

- Flutter SDK 3.x
- Android Studio with Android Emulator (API 30+)

### Installation

```powershell
cd d:\Schemora\frontend
flutter pub get
```

### Running on Android Emulator

```powershell
flutter run -d <emulator_device_id>
```

### API Base URL Configuration

Located in `lib/core/network/api_client.dart`:
```dart
// For Android Emulator: Use 10.0.2.2 to reach host machine
const String baseUrl = 'http://10.0.2.2:8000/api/v1';
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
- `language`: Optional ISO language code hint

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

### GET `/api/v1/ai/knowledge-base/status`

Get knowledge base statistics.

### POST `/api/v1/ai/knowledge-base/index`

Trigger full re-indexing of schemes dataset.

---

## 9. Acceptance Test Results

### Requirement 1: Search via Chatbot

| # | Test Query | Expected Behavior | Status |
|---|-----------|-------------------|--------|
| 1 | "hello" | Greeting response (no scheme clarification) | ✅ PASS |
| 2 | "hi" | Greeting response | ✅ PASS |
| 3 | "What is a government scheme?" | Definition response | ✅ PASS |
| 4 | "Tell me about PM-KISAN" | PM-KISAN scheme overview | ✅ PASS |
| 5 | "Documents for PM-KISAN" | Document checklist | ✅ PASS |
| 6 | "How to apply for PM-KISAN" | Step-by-step process | ✅ PASS |
| 7 | "Schemes for farmers in Maharashtra" | List of farmer schemes | ✅ PASS |
| 8 | "Scholarships for students" | List of scholarships | ✅ PASS |
| 9 | "Compare PM-KISAN vs PM Internship" | Comparison table | ✅ PASS |
| 10 | "What are the eligibilty criteria for PM-KISAN?" (typo) | Correct eligibility info | ✅ PASS |
| 11 | "xyzabc" | "I'm not sure what you mean" | ✅ PASS |

### Requirement 2: Voice Support

| # | Test | Expected | Status |
|---|------|----------|--------|
| 1 | Tap mic button | "Listening..." UI shown | ✅ |
| 2 | Speak "hello" | Text appears in input field | ✅ |
| 3 | Speech ends | Query sent to chatbot | ✅ |
| 4 | Bot responds | TTS plays response audio | ✅ |
| 5 | Error handling | Clear error SnackBar shown | ✅ |

### Requirement 3: Multilingual

| # | Query | Language | Expected Response Language | Status |
|---|-------|----------|--------------------------|--------|
| 1 | "पीएम किसान क्या है?" | hi | Hindi response only | ✅ |
| 2 | "PM Kisan ke liye documents?" | hi (Hinglish) | Hindi/English response | ✅ |
| 3 | "PM Kisan schemana documents?" | gu | Gujarati response | ✅ |
| 4 | "hello" | en | English greeting | ✅ |

### Requirement 4: Accurate Answers

| # | Test | Expected | Status |
|---|------|----------|--------|
| 1 | PM-KISAN response contains correct ₹6000 amount | From verified KB | ✅ |
| 2 | Citations contain scheme-specific URLs | No india.gov.in generic links | ✅ |
| 3 | Greeting doesn't return scheme clarification | Intent detection accurate | ✅ |
| 4 | Typo tolerance ("eligibilty" → ELIGIBILITY intent) | Fuzzy matching works | ✅ |

### Requirement 5: Documentation

This document. ✅

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

**Workaround**: Already handled via multi-host fallback in `AIRepositoryImpl`.

### Knowledge Base (Development)

**Issue**: Development mode uses SQLite + TF-IDF embeddings (not pgvector).

**Impact**: Retrieval quality is lower than production (pgvector + dense embeddings).

**Fix**: Run PostgreSQL with pgvector extension for production-grade retrieval.

### Groq API Rate Limits

**Issue**: Groq free tier has rate limits (30 requests/minute on llama-3.3-70b).

**Workaround**: The backend has a model fallback chain: `llama-3.3-70b-versatile` → `llama-3.1-8b-instant` → `llama3-8b-8192`.

---

*Documentation version: 1.0 — Last updated: 2026-09-17*
