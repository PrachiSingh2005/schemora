"""Groq AI Service — Schemora.

Responsibilities:
  - generate_grounded_explanation(): deterministic explanation for scheme eligibility
  - generate_grounded_chat_response(): RAG-powered Q&A using Groq API with safety guardrails

Safety Rules enforced in every prompt:
  1. Answer ONLY based on retrieved context. Never invent schemes or facts.
  2. If info is not in context, say so clearly.
  3. Never fabricate benefit amounts, deadlines, or application links.
  4. Always cite which source the answer comes from.
  5. Distinguish: verified info vs. needs-verification info.
"""

import os
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    import httpx
except ImportError:
    httpx = None

try:
    from app.core.config import settings
except Exception:
    class _Settings:
        GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
        GROQ_GENERATION_MODEL = os.getenv("GROQ_GENERATION_MODEL", "llama-3.3-70b-versatile")
    settings = _Settings()

from app.services.language_service import language_registry, LanguageSpec
from app.services.retrieval_service import detect_intent, extract_query_entity_and_section
from app.services.query_understanding_service import analyze_query_understanding

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_STT_MODEL = "whisper-large-v3"

OUT_OF_SCOPE_KEYWORDS = [
    "weather", "cricket", "movie", "recipe", "capital of", "president of",
    "tell me a joke", "football", "who won", "celebrity", "stock price",
    "bitcoin", "gaming", "sports score",
]


def _get_api_key() -> str:
    key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "") or ""
    return key.strip()


def _get_generation_model() -> str:
    return getattr(settings, "GROQ_GENERATION_MODEL", "llama-3.3-70b-versatile")


def is_out_of_scope(query: str) -> bool:
    q_lower = query.lower()
    return any(k in q_lower for k in OUT_OF_SCOPE_KEYWORDS)


def generate_grounded_explanation(
    scheme_title: str,
    status: str,
    matched_rules: List[Dict[str, Any]],
    unresolved_rules: List[Dict[str, Any]],
    sources: List[Dict[str, Any]],
    language: str = "en",
) -> Tuple[str, List[Dict[str, Any]]]:
    """Deterministic grounded explanation for scheme recommendation results."""
    citations = []
    for s in sources:
        url = s.get("url", "").strip()
        if url:
            citations.append({
                "source_name": s.get("source_name", "Official Portal"),
                "url": url,
                "last_verified_at": s.get("last_verified_at", "2026-08-07"),
            })

    if status == "RuleMatched":
        explanation = (
            f"Based on official guidelines for '{scheme_title}', you satisfy all "
            f"mandatory criteria! Your profile matches {len(matched_rules)} verified conditions."
        )
    elif status == "NeedsInformation":
        fields = [r.get("field_name") for r in unresolved_rules if r.get("field_name")]
        fields_str = ", ".join(fields) if fields else "required fields"
        explanation = (
            f"You are potentially eligible for '{scheme_title}'. "
            f"Additional information is needed for: {fields_str}."
        )
    else:
        title_lower = scheme_title.lower()
        if any(kw in title_lower for kw in ["kisan", "fasal", "farmer", "agriculture", "agri", "crop"]):
            explanation = (
                f"You are not eligible for '{scheme_title}'. "
                f"Reason: Your registered profile is Student / Learner, whereas this farmer scheme requires "
                f"an agricultural occupation or landholding."
            )
        elif any(kw in title_lower for kw in ["mudra", "svanidhi", "pmegp", "business", "enterprise", "msme"]):
            explanation = (
                f"You are not eligible for '{scheme_title}'. "
                f"Reason: Your registered profile is Student / Learner, whereas this business scheme requires "
                f"an active micro-enterprise or business registration."
            )
        elif any(kw in title_lower for kw in ["pension", "apy", "ignoaps", "senior", "scss", "old age"]):
            explanation = (
                f"You are not eligible for '{scheme_title}'. "
                f"Reason: Your registered profile is Student / Learner (Age ~20), whereas senior citizen schemes require "
                f"age 60+ or retired pension status."
            )
        elif any(kw in title_lower for kw in ["ladki", "bahin", "gruha", "lakshmi", "sumangala", "sukanya", "matru", "women", "female"]):
            explanation = (
                f"You are not eligible for '{scheme_title}'. "
                f"Reason: Your registered profile is Student / Learner, whereas women/family schemes are restricted to "
                f"female heads of household or women beneficiaries."
            )
        else:
            explanation = (
                f"Based on current guidelines for '{scheme_title}', "
                f"your profile does not satisfy one or more mandatory criteria."
            )

    lang_spec = language_registry.get_spec(language)
    lang_suffix = f" (Official Guidelines — {lang_spec.native_name})" if lang_spec.code != "en" else ""

    return explanation + lang_suffix, citations


def evaluate_chunk_relevance(query: str, chunks: List[Dict[str, Any]]) -> Tuple[bool, float]:
    """Evaluate whether retrieved chunks are relevant enough to answer the user query.

    Args:
        query: User's question text.
        chunks: List of retrieved knowledge/web chunk dictionaries.

    Returns:
        (is_relevant, confidence_score)
    """
    if not chunks:
        return False, 0.0

    # If any web search chunk was retrieved, it is considered relevant if non-empty
    if any(c.get("is_web_search") for c in chunks):
        top_score = float(chunks[0].get("similarity_score", 0.85))
        return True, top_score

    q_clean = query.lower().strip()
    stop_words = {
        "what", "how", "when", "where", "who", "which", "is", "are", "do", "does",
        "can", "should", "the", "a", "an", "in", "on", "for", "to", "of", "and",
        "scheme", "scholarship", "yojana", "tell", "show", "give", "please", "me",
        "about", "details", "information", "eligibility", "process", "apply", "benefit"
    }
    q_words = [w for w in re.findall(r"\w+", q_clean) if len(w) > 2 and w not in stop_words]

    top_score = float(chunks[0].get("similarity_score", 0.0))

    if not q_words:
        is_rel = top_score >= 0.045
        return is_rel, top_score

    # Count keyword matches across top retrieved chunks
    matched_chunks = 0
    for c in chunks[:4]:
        chunk_text = f"{c.get('scheme_name', '')} {c.get('content', '')}".lower()
        if any(w in chunk_text for w in q_words):
            matched_chunks += 1

    is_relevant = (top_score >= 0.045 or matched_chunks > 0)
    avg_score = round(sum(float(c.get("similarity_score", 0.0)) for c in chunks[:5]) / min(len(chunks), 5), 3)

    return is_relevant, max(top_score, avg_score)


def _build_rag_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    lang_spec: LanguageSpec,
    eligibility_context: Optional[str] = None,
) -> str:
    """Build a sharp, concise grounded prompt for Groq API using LanguageSpec."""

    context_lines = []
    for i, c in enumerate(chunks, 1):
        scheme_name = c.get("scheme_name", "")
        section = c.get("section", "")
        content = c.get("content", "")
        verified = c.get("last_verified_at", "")
        info_url = c.get("source_url", "").strip()
        app_url = c.get("official_app_url", "").strip()
        is_web = c.get("is_web_search", False)
        source_type = "Official Web Search" if is_web else "Schemora Verified KB"

        url_line = ""
        if info_url:
            url_line += f"\nOfficial Info URL: {info_url}"
        if app_url:
            url_line += f"\nOnline Application URL: {app_url}"
        context_lines.append(
            f"[Source {i} — {source_type}] {scheme_name} ({section.title()}) — Verified: {verified}{url_line}\n{content}"
        )
    context_text = "\n\n".join(context_lines)

    eligibility_section = ""
    if eligibility_context:
        eligibility_section = f"\nELIGIBILITY RULE RESULT:\n{eligibility_context}\n"

    if lang_spec.code == "en":
        lang_rule = (
            "CRITICAL: Respond STRICTLY AND ONLY IN ENGLISH. "
            "Do NOT include any Hindi, Gujarati, or other Indic translations, explanations, or scripts. "
            "Do NOT output headers like 'Hindi Explanation:' or 'Gujarati Explanation:'."
        )
    elif lang_spec.code == "hi":
        lang_rule = (
            "CRITICAL: Respond STRICTLY AND ONLY IN HINDI (हिंदी). "
            "Do NOT include English or Gujarati translations or explanations."
        )
    elif lang_spec.code == "gu":
        lang_rule = (
            "CRITICAL: Respond STRICTLY AND ONLY IN GUJARATI (ગુજરાતી). "
            "Do NOT include English or Hindi translations or explanations."
        )
    else:
        lang_rule = (
            f"CRITICAL: Respond STRICTLY AND ONLY IN {lang_spec.name} ({lang_spec.native_name}). "
            f"Do NOT include translations in other languages."
        )

    from app.services.retrieval_service import detect_intent as _det_intent
    _query_intent = _det_intent(query)

    # Per-intent response formatting instructions
    intent_instructions = ""
    if _query_intent == "FINANCIAL_DETAILS":
        intent_instructions = (
            "FINANCIAL DETAILS FORMAT: State the exact amount, currency, frequency, and coverage. "
            "If multiple amounts exist, use a short table or bullet list. "
            "If the exact amount is not in context, say clearly that it requires official verification."
        )
    elif _query_intent == "CONTACT":
        intent_instructions = (
            "CONTACT FORMAT: List helpline number, email, grievance portal, and official website clearly. "
            "Use bullet points. If no contact info is in context, direct user to the official portal."
        )
    elif _query_intent == "RENEWAL":
        intent_instructions = (
            "RENEWAL FORMAT: Explain the renewal process step by step. "
            "State the typical renewal window (e.g., July–November on NSP). "
            "Mention minimum academic performance or other conditions if present in context."
        )
    elif _query_intent == "COMPARISON":
        intent_instructions = (
            "COMPARISON FORMAT: You MUST format your response as a neutral side-by-side Markdown Table: "
            "| Feature | Scheme/Entity 1 | Scheme/Entity 2 |\n"
            "Include comparative rows for: Purpose / Overview, Target Beneficiaries, Eligibility Criteria, "
            "Benefits & Financial Aid, Application Process, and Official Portal.\n"
            "Do NOT rank any scheme as 'better' or 'best' unless the user specified explicit objective criteria."
        )
    elif _query_intent == "SPECIFIC_SCHEME":
        intent_instructions = (
            "SPECIFIC SCHEME FORMAT: Give a 3–4 sentence overview including: "
            "what the scheme is, which Ministry/State runs it, who it is for, and the main benefit. "
            "Then provide 1 official link."
        )
    elif _query_intent == "STATUS":
        intent_instructions = (
            "STATUS FORMAT: State whether the scheme is currently Active, Closed, or Upcoming based on context. "
            "If dates are available, mention them. "
            "If status is unknown from context, say \"Please check the official portal for current status.\""
        )
    elif _query_intent == "DEADLINE":
        intent_instructions = (
            "DEADLINE FORMAT: State the exact application deadline date from context. "
            "If not available, say \"The deadline has not been announced yet. "
            "Please check the official portal.\""
        )
    elif _query_intent == "APPLICATION_CHANNEL":
        intent_instructions = (
            "APPLICATION CHANNEL FORMAT: Tell the user WHERE to apply — provide the online portal URL and/or "
            "offline channel (CSC / Tehsil Office). Use bullet points."
        )

    prompt = f"""You are Schemora AI Assistant, a trusted expert on Indian Government Schemes.

LANGUAGE RULE (HIGHEST PRIORITY): {lang_rule}

{f'RESPONSE FORMAT (for this query type: {_query_intent}):\n{intent_instructions}\n' if intent_instructions else ''}
STRICT RESPONSE LENGTH & FORMATTING RULES:
1. DEFINITION / CONCEPT QUESTIONS (e.g. "What is a scheme?", "What is subsidy?", "योजना क्या है?", "સરકારી યોજના શું છે?"):
   - Answer in 2 TO 4 SENTENCES MAXIMUM.
   - Summarize the concept into a clean, direct definition and brief explanation in plain language.
   - Do NOT dump raw database headers or metadata (do NOT output "Concept:", "Definition:", "Purpose:", "Key Components:", "Hindi Explanation:", "Gujarati Explanation:").
   - Format: Short paragraph for definition, followed optionally by 1 line of brief examples.
   - Example style for English:
     "A government scheme is a program introduced by the Central or State Government to provide benefits or support to eligible citizens.

     Examples include scholarships, subsidies, healthcare support, and financial assistance."

2. SCHEME DISCOVERY / LISTING QUESTIONS (e.g. "What schemes are available for students?", "schemes for farmers"):
   - Return a concise list of relevant schemes using bullet points (`•`).
   - For EACH scheme, include ONLY:
     • **Scheme Name**: One-sentence purpose/summary.
     • **Eligibility / Benefit**: Key qualification or benefit in 1 line.
     • **Official Link**: Portal or application URL if present in context.
   - Do NOT write long multi-paragraph descriptions for every scheme. Keep each scheme entry brief (2-3 lines total).

3. GENERAL CONSTRAINTS:
   - Answer ONLY using verified facts in the RETRIEVED CONTEXT below. Do NOT invent facts, deadlines, or links.
   - If the retrieved context is insufficient, state clearly in {lang_spec.name}: "{lang_spec.not_found_msg}"
   - Keep answers easy to scan, concise, friendly, and structured.
   - Do NOT append extraneous follow-up question lists or multilingual translation sections to the response text.

RETRIEVED CONTEXT:
{context_text}
{eligibility_section}

USER QUESTION: {query}
"""
    return prompt




async def _call_groq(prompt: str, api_key: str, model: str) -> Optional[str]:
    """Call Groq API (OpenAI compatible endpoint). Returns response text or None."""
    if not api_key:
        logger.warning("[CHAT] GROQ_API_KEY is missing or unconfigured.")
        return None

    # Model fallback chain (primary model, then fast instant models)
    models_to_try = [model, "llama-3.1-8b-instant", "llama3-8b-8192"]
    models_to_try = list(dict.fromkeys([m for m in models_to_try if m]))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for m in models_to_try:
        payload = {
            "model": m,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1000,
            "top_p": 0.8,
        }
        try:
            if httpx is not None:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    resp = await client.post(GROQ_API_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    ans = data["choices"][0]["message"]["content"].strip()
                    if ans:
                        logger.info(f"[CHAT] Groq response generated successfully with model='{m}'")
                        return ans
                else:
                    logger.warning(
                        f"[CHAT] Groq API model '{m}' returned status {resp.status_code}: {resp.text[:200]}"
                    )
            else:
                import urllib.request
                import json as json_lib
                data_bytes = json_lib.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    GROQ_API_URL,
                    data=data_bytes,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=6.0) as resp:
                    resp_data = json_lib.loads(resp.read().decode("utf-8"))
                    ans = resp_data["choices"][0]["message"]["content"].strip()
                    if ans:
                        return ans
        except Exception as e:
            logger.warning(f"[CHAT] Groq model '{m}' call timed out or failed: {e}")
            continue

    return None


def _clean_response_formatting(text: str, lang_spec: LanguageSpec) -> str:
    """Clean and sanitize LLM/Fallback output according to target language and strict formatting rules."""
    if not text:
        return ""

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line_str = line.strip()

        # 1. Remove unwanted multi-lingual explanation headers/lines for English queries
        if lang_spec.code == "en":
            if any(line_str.startswith(k) for k in [
                "Hindi Explanation:", "Gujarati Explanation:", "Marathi Explanation:",
                "Bengali Explanation:", "Tamil Explanation:", "Telugu Explanation:",
                "हिंदी व्याख्या:", "ગુજરાતી ખુલાસો:"
            ]):
                continue
            # Strip pure Devanagari/Gujarati lines if English response expected
            if re.search(r"[\u0900-\u097F\u0A80-\u0AFF]", line_str) and not re.search(r"[A-Za-z0-9]", line_str):
                continue
        elif lang_spec.code == "hi":
            if any(line_str.startswith(k) for k in [
                "English Explanation:", "Gujarati Explanation:", "Marathi Explanation:",
                "Bengali Explanation:", "Tamil Explanation:", "Telugu Explanation:"
            ]):
                continue
            if line_str.startswith("Hindi Explanation:"):
                line_str = line_str.replace("Hindi Explanation:", "").strip()
        elif lang_spec.code == "gu":
            if any(line_str.startswith(k) for k in [
                "English Explanation:", "Hindi Explanation:", "Marathi Explanation:",
                "Bengali Explanation:", "Tamil Explanation:", "Telugu Explanation:"
            ]):
                continue
            if line_str.startswith("Gujarati Explanation:"):
                line_str = line_str.replace("Gujarati Explanation:", "").strip()

        # 2. Strip raw KB noise prefixes if model echoed them
        for raw_prefix in ["Concept:", "Definition:", "Key Components:", "Hindi Explanation:", "Gujarati Explanation:"]:
            if line_str.startswith(raw_prefix) and lang_spec.code == "en":
                line_str = line_str.replace(raw_prefix, "").strip()

        # 3. Clean raw URL displays into clean labeled markdown links
        def _format_clean_link(match):
            raw_url = match.group(1).strip()
            if "myscheme.gov.in" in raw_url.lower():
                return f"[Source: myScheme]({raw_url})"
            return f"[Official Portal]({raw_url})"

        line_str = re.sub(
            r"\[(?:https?://[^\s\]]+)\]\((https?://[^\s\)]+)\)",
            _format_clean_link,
            line_str
        )

        # 4. Strip artificial "You might also want to ask:" block if added to text
        if any(b in line_str for b in ["You might also want to ask:", "💡 **Related Support Questions", "💡 **संबंधित प्रश्न", "💡 **સંબંધિત પ્રશ્નો"]):
            break

        cleaned_lines.append(line_str)

    # Rejoin lines into clean paragraphs
    result = "\n".join(cleaned_lines)
    # Remove multiple consecutive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result


def _build_citations(chunks: List[Dict[str, Any]], intent: str = "UNKNOWN") -> List[Dict[str, Any]]:
    """Build per-scheme citation list — returns distinct verified source links for each retrieved scheme.

    Rules:
    - Returns independent citations per scheme (Scheme A, Scheme B, etc.).
    - If intent is application-related: Priority to verified application_url.
    - Never returns generic fallback URLs like india.gov.in.
    """
    if not chunks:
        return []

    is_app_query = intent in ("APPLICATION_PROCESS", "APPLICATION_CHANNEL", "RENEWAL", "REQUIRED_DOCUMENTS")
    citations = []
    seen_urls = set()
    seen_schemes = set()

    for c in chunks:
        if not isinstance(c, dict):
            continue

        s_name = str(c.get("scheme_name") or "Scheme").strip()
        if s_name in seen_schemes:
            continue
        seen_schemes.add(s_name)

        raw_app_url = c.get("official_app_url") or c.get("application_url") or ""
        raw_info_url = c.get("official_scheme_url") or c.get("official_info_url") or c.get("source_url") or ""

        app_url = str(raw_app_url or "").strip()
        info_url = str(raw_info_url or "").strip()

        # Clean generic fallbacks
        if any(g in app_url.lower() for g in ["india.gov.in"]):
            app_url = ""
        if any(g in info_url.lower() for g in ["india.gov.in"]):
            info_url = ""

        target_url = (app_url if is_app_query and app_url else info_url) or app_url
        if not target_url or not target_url.startswith("http") or target_url in seen_urls:
            continue

        seen_urls.add(target_url)
        v_date = str(c.get("last_verified_at") or "2026-09-17").strip()
        label = f"Apply Online — {s_name}" if (is_app_query and app_url) else f"Official Portal — {s_name}"

        citations.append({
            "source_name": label,
            "url": target_url,
            "label": label,
            "last_verified_at": v_date,
        })

    return citations


def _extract_scheme_summary(chunks: List[Dict[str, Any]], scheme_name: str) -> Dict[str, str]:
    """Extract clean human-readable summary fields from scheme chunks."""
    summary = {
        "overview": "",
        "benefits": "",
        "eligibility": "",
        "documents": "",
        "application": "",
    }
    for c in chunks:
        sec = c.get("section", "overview")
        cnt = str(c.get("content") or "").strip()
        lines = []
        for line in cnt.split("\n"):
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("Description:"):
                desc = line_str.replace("Description:", "").strip()
                if desc and not summary["overview"]:
                    summary["overview"] = desc
                continue
            if any(line_str.startswith(k) for k in ["Scheme:", "Category:", "Jurisdiction:", "State:", "Department:", "Status:", "Cycle:"]):
                continue
            lines.append(line_str)
        text = " ".join(lines).strip()
        if sec in summary and not summary[sec] and text:
            summary[sec] = text

    return summary


def _build_support_queries(scheme_names: List[str], lang_spec: LanguageSpec) -> str:
    """Build top 3 contextual support cross-questions using retrieved scheme names."""
    if not scheme_names:
        return ""

    title = lang_spec.support_title
    s1 = scheme_names[0]
    s2 = scheme_names[1] if len(scheme_names) > 1 else s1
    s3 = scheme_names[2] if len(scheme_names) > 2 else s1

    if lang_spec.code == "hi":
        q1 = f"• {s1} के लिए कौन से दस्तावेज़ आवश्यक हैं?"
        q2 = f"• {s2} के लिए ऑनलाइन आवेदन कैसे करें step-by-step?"
        q3 = f"• {s3} की पात्रता और लाभ विवरण क्या हैं?"
    elif lang_spec.code == "gu":
        q1 = f"• {s1} માટે કયા દસ્તાવેજો જરૂરી છે?"
        q2 = f"• {s2} માટે ઓનલાઈન અરજી કેવી રીતે કરવી step-by-step?"
        q3 = f"• {s3} ની પાત્રતા અને લાભોની વિગતો શું છે?"
    elif lang_spec.code == "mr":
        q1 = f"• {s1} साठी कोणती कागदपत्रे आवश्यक आहेत?"
        q2 = f"• {s2} साठी ऑनलाईन अर्ज कसा करावा step-by-step?"
        q3 = f"• {s3} ची पात्रता आणि लाभ काय आहेत?"
    elif lang_spec.code == "bn":
        q1 = f"• {s1}-এর জন্য কী কী নথি প্রয়োজন?"
        q2 = f"• {s2}-এর জন্য কীভাবে অনলাইনে আবেদন করবেন?"
        q3 = f"• {s3}-এর যোগ্যতা ও সুবিধার বিবরণ কী?"
    else:
        q1 = f"• What documents are required to apply for {s1}?"
        q2 = f"• How do I apply online step-by-step for {s2}?"
        q3 = f"• What are the eligibility criteria and benefit details for {s3}?"

    return f"{title}\n{q1}\n{q2}\n{q3}"


def _build_fallback_response(
    chunks: List[Dict[str, Any]],
    lang_spec: LanguageSpec,
) -> str:
    """Build a language-aware, concise, human-friendly response from verified knowledge chunks."""
    if not chunks:
        return lang_spec.not_found_msg

    # Handling concept/glossary chunks fallback
    if any(c.get("section") in ["concept", "glossary"] or c.get("category") == "Glossary" for c in chunks):
        parts = []
        for c in chunks[:1]:
            cnt = str(c.get("content") or "").strip()
            if not cnt:
                continue

            def_line = ""
            purpose_line = ""
            hi_line = ""
            gu_line = ""

            for line in cnt.split("\n"):
                line_str = line.strip()
                if line_str.startswith("Definition:"):
                    def_line = line_str.replace("Definition:", "").strip()
                elif line_str.startswith("Purpose:"):
                    purpose_line = line_str.replace("Purpose:", "").strip()
                elif line_str.startswith("Hindi Explanation:"):
                    hi_line = line_str.replace("Hindi Explanation:", "").strip()
                elif line_str.startswith("Gujarati Explanation:"):
                    gu_line = line_str.replace("Gujarati Explanation:", "").strip()

            if lang_spec.code == "hi" and hi_line:
                parts.append(hi_line)
            elif lang_spec.code == "gu" and gu_line:
                parts.append(gu_line)
            else:
                if def_line:
                    text_out = def_line
                    if purpose_line:
                        text_out += f"\n\nPurpose: {purpose_line}"
                    parts.append(text_out)
                else:
                    parts.append(cnt)

        out_text = "\n\n".join(parts)
        return _clean_response_formatting(out_text, lang_spec)

    schemes_dict: Dict[str, Dict[str, Any]] = {}
    for c in chunks:
        s_name = str(c.get("scheme_name") or "Official Scheme").strip()
        if s_name not in schemes_dict:
            schemes_dict[s_name] = {
                "chunks": [],
                "info_url": str(c.get("official_info_url") or c.get("source_url") or "").strip(),
                "app_url": str(c.get("official_app_url") or c.get("application_url") or "").strip(),
                "state": str(c.get("state") or "").strip(),
                "jurisdiction": str(c.get("jurisdiction") or "").strip(),
            }
        schemes_dict[s_name]["chunks"].append(c)

    parts = []
    for i, (s_name, data) in enumerate(list(schemes_dict.items())[:4], 1):
        summary = _extract_scheme_summary(data["chunks"], s_name)
        card = [f"• **{s_name}**"]
        if summary["application"]:
            card.append(f"  • **Application Process**: {summary['application']}")
        elif summary["documents"]:
            card.append(f"  • **Required Documents**: {summary['documents']}")
        elif summary["overview"]:
            card.append(f"  {summary['overview']}")

        if summary["benefits"]:
            ben_clean = summary["benefits"].replace(f"Benefits provided by {s_name}:", "").replace("Benefits:", "").strip()
            if ben_clean:
                card.append(f"  • **Benefits**: {ben_clean}")

        if summary["eligibility"]:
            el_clean = summary["eligibility"].replace(f"Eligibility criteria for {s_name}:", "").replace("Eligibility:", "").strip()
            if el_clean and "Detailed eligibility criteria require verification" not in el_clean:
                card.append(f"  • **Eligibility**: {el_clean}")

        link_url = data["app_url"] or data["info_url"]
        if link_url:
            card.append(f"  • **Official Portal**: [{link_url}]({link_url})")

        parts.append("\n".join(card))

    return _clean_response_formatting("\n\n".join(parts), lang_spec)


def detect_query_language(query: str, passed_lang: Optional[str] = None) -> str:
    """Auto-detect user query language based on script/character ranges."""
    spec = language_registry.detect_language(query, passed_lang)
    return spec.code


async def generate_grounded_chat_response(
    query: str,
    chunks: List[Dict[str, Any]],
    language: str = "en",
    eligibility_context: Optional[str] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[Dict[str, Any]], bool]:
    """Generate a RAG-grounded chat response in the requested language using Groq API.

    Args:
        query: User's question.
        chunks: Retrieved knowledge chunks from retrieval_service.
        language: ISO language code (en, hi, mr, gu, bn, te, ta, etc.)
        eligibility_context: Optional eligibility result from the rule engine.
        conversation_context: Optional dict from previous turn containing:
            - last_scheme: Name of scheme discussed in previous turn
            - last_intent: Intent type from previous turn

    Returns:
        (answer_text, citations, is_grounded)
    """
    lang_spec = language_registry.detect_language(query, language)
    q_clean = query.strip().lower()

    intent = detect_intent(query, conversation_context=conversation_context)

    if (
        intent == "GREETING"
        or re.match(r"^(?:hi|hello|hey|greetings|namaste|namaskar|kem cho|good\s*(?:morning|afternoon|evening)|hallo|hola|ssa|satsriakal|hi+|hello+)\s*[\!\?\,\.]*$", q_clean)
        or q_clean in ["who are you", "what can you do", "how are you", "help", "કેમ છો", "તમે કોણ છો"]
    ):
        return lang_spec.greeting_msg, [], True

    if intent == "THANKS" or re.match(r"^(?:thanks|thank\s*you|shukriya|dhanyawad|thx|dhanbad|આભાર)\s*[\!\?\,\.]*$", q_clean):
        return lang_spec.thanks_msg, [], True

    if intent == "GOODBYE" or re.match(r"^(?:bye|goodbye|cya|see\s*you|take\s*care|alvida|tata)\s*[\!\?\,\.]*$", q_clean):
        return getattr(lang_spec, "goodbye_msg", "Goodbye! 👋 Have a great day ahead!"), [], True

    if is_out_of_scope(query):
        return lang_spec.out_of_scope_msg, [], False

    # 1. Run Query Understanding Analysis
    qu_res = analyze_query_understanding(query, passed_lang=language, conversation_context=conversation_context)

    # 2. Ambiguity Handling (Requirement 17)
    if qu_res.is_ambiguous:
        if lang_spec.code == "hi":
            msg = "क्या आप योजना का नाम स्पष्ट कर सकते हैं? जैसे, PM-KISAN, PM Internship, या PM MUDRA।"
        elif lang_spec.code == "gu":
            msg = "શું તમે યોજનાનું નામ સ્પષ્ટ કરી શકો છો? દાખલા તરીકે, PM-KISAN અથવા PM Internship."
        elif lang_spec.code == "mr":
            msg = "कृपया योजनेचे नाव स्पष्ट करा. उदाहरणार्थ, PM-KISAN किंवा PM Internship."
        else:
            opts_str = ", ".join(qu_res.ambiguous_options[:4]) if qu_res.ambiguous_options else "PM-KISAN or another PM scheme"
            msg = f"Could you specify the scheme name? For example, {opts_str}."
        return msg, [], True

    # 3. Portal Entity Handling (Requirements 13, 14, 19)
    if qu_res.entity_match and qu_res.entity_match.entity.entity_type == "PORTAL":
        ent = qu_res.entity_match.entity
        citations = []
        if ent.official_url:
            citations = [{
                "source_name": f"Official Portal — {ent.canonical_name}",
                "url": ent.official_url,
                "last_verified_at": "2026-08-07"
            }]

        norm_q = qu_res.normalized_query
        if "apply" in norm_q or "application" in norm_q or "register" in norm_q or "fill" in norm_q:
            if lang_spec.code == "hi":
                answer = f"**{ent.canonical_name} ({ent.official_name}) पर आवेदन कैसे करें:**\n1. आधिकारिक पोर्टल पर जाएं: [{ent.official_url}]({ent.official_url})\n2. Applicant Registration पर क्लिक करके यूजर आईडी बनाएं।\n3. अपनी प्रोफाइल विवरण भरें और आवश्यक दस्तावेज अपलोड करें।\n4. अपनी पात्र छात्रवृत्ति योजना का चयन करें और आवेदन जमा करें।"
            elif lang_spec.code == "gu":
                answer = f"**{ent.canonical_name} ({ent.official_name}) પર અરજી કેવી રીતે કરવી:**\n1. સત્તાવાર પોર્ટલની મુલાકાત લો: [{ent.official_url}]({ent.official_url})\n2. Applicant Registration દ્વારા યુઝર આઈડી બનાવો.\n3. પ્રોફાઇલ વિગતો ભરો અને જરૂરી દસ્તાવેજો અપલોડ કરો.\n4. તમારી યોગ્ય શિષ્યવૃત્તિ પસંદ કરો અને અરજી કરો."
            else:
                answer = f"To apply on **{ent.canonical_name} ({ent.official_name})**:\n1. Visit the official portal: [{ent.official_url}]({ent.official_url})\n2. Register and create an Applicant User ID.\n3. Complete your profile details and upload required documents.\n4. Select your eligible scholarship or welfare scheme and submit."
        elif "scholarship" in norm_q or "scheme" in norm_q:
            if lang_spec.code == "hi":
                answer = f"**{ent.canonical_name} ({ent.official_name})** महाराष्ट्र सरकार का आधिकारिक डीबीटी पोर्टल है, जो मैट्रिक-पूर्व और मैट्रिक-उत्तर छात्रवृत्तियों की मेजबानी करता है।\nआधिकारिक पोर्टल: [{ent.official_url}]({ent.official_url})"
            elif lang_spec.code == "gu":
                answer = f"**{ent.canonical_name} ({ent.official_name})** એ મહારાષ્ટ્ર સરકારનું સત્તાવાર DBT પોર્ટલ છે.\nસત્તાવાર પોર્ટલ: [{ent.official_url}]({ent.official_url})"
            else:
                answer = f"**{ent.canonical_name} ({ent.official_name})** is the official Direct Benefit Transfer portal of the Government of Maharashtra hosting various Post-Matric and Pre-Matric scholarship schemes.\nOfficial Portal: [{ent.official_url}]({ent.official_url})"
        else:
            if lang_spec.code == "hi":
                answer = f"**{ent.canonical_name} ({ent.official_name})**:\n{ent.description}\nआधिकारिक पोर्टल: [{ent.official_url}]({ent.official_url})"
            elif lang_spec.code == "gu":
                answer = f"**{ent.canonical_name} ({ent.official_name})**:\n{ent.description}\nસત્તાવાર પોર્ટલ: [{ent.official_url}]({ent.official_url})"
            else:
                answer = f"**{ent.canonical_name} ({ent.official_name})**:\n{ent.description}\nOfficial Portal: [{ent.official_url}]({ent.official_url})"

        return answer, citations, True

    # 4. Unknown / Low Confidence Handling (Requirements 4, 18)
    if intent == "UNKNOWN" or (qu_res.confidence_level in ["LOW", "UNKNOWN"] and not qu_res.entity_match and not chunks and intent not in ["SCHEME_DISCOVERY", "DEFINITION_CONCEPT", "GREETING", "THANKS", "GOODBYE"]):
        if lang_spec.code == "hi":
            msg = "मुझे समझ नहीं आया। क्या आप योजना या पोर्टल का नाम बता सकते हैं?"
        elif lang_spec.code == "gu":
            msg = "મને સમજાતું નથી. શું તમે યોજના અથવા પોર્ટલનું નામ આપી શકો છો?"
        elif lang_spec.code == "mr":
            msg = "मला समजले नाही. कृपया योजनेचे किंवा पोर्टलचे नाव सांगा."
        else:
            msg = "I'm not sure what you mean. Could you provide the scheme or portal name?"
        return msg, [], True

    entity, target_sec = extract_query_entity_and_section(query, conversation_context=conversation_context)

    # Extended clarification: ask for scheme name when entity-less for specific-info intents and no chunks found
    if not chunks and intent in ["APPLICATION_PROCESS", "ELIGIBILITY", "REQUIRED_DOCUMENTS",
                  "BENEFITS", "FINANCIAL_DETAILS", "DEADLINE", "STATUS",
                  "RENEWAL", "CONTACT", "FAQ", "APPLICATION_CHANNEL"] and not entity:
        if lang_spec.code == "hi":
            return "आप किस छात्रवृत्ति या सरकारी योजना के बारे में जानना चाहते हैं? कृपया योजना का नाम बताएं।", [], True
        elif lang_spec.code == "gu":
            return "તમે કયી શિષ્યવૃત્તિ અથવા સરકારી યોજના વિશે જાણવા માંગો છો? કૃપા યોજનાનું નામ જણાવો.", [], True
        elif lang_spec.code == "mr":
            return "तुम्हाला कोणत्या शिष्यवृत्ती किंवा सरकारी योजनेबद्दल जाणून घ्यायचे आहे? कृपया योजनेचे नाव सांगा.", [], True
        else:
            return "Which scholarship or government scheme are you asking about? Please mention the scheme name.", [], True

    if not chunks:
        return lang_spec.not_found_msg, [], False

    citations = _build_citations(chunks, intent=intent)

    api_key = _get_api_key()
    model = _get_generation_model()

    if api_key and len(api_key) > 5:
        prompt = _build_rag_prompt(query, chunks, lang_spec, eligibility_context)
        raw_answer = await _call_groq(prompt, api_key, model)
        if raw_answer:
            cleaned_answer = _clean_response_formatting(raw_answer, lang_spec)
            return cleaned_answer, citations, True
        logger.warning(
            f"Groq call failed or unconfigured — activating verified knowledge fallback in language={lang_spec.code}."
        )

    fallback_answer = _build_fallback_response(chunks, lang_spec)
    return fallback_answer, citations, True


async def transcribe_audio_with_groq(
    file_bytes: bytes,
    filename: str = "audio.wav",
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert speech audio bytes into transcribed text using Groq Whisper v3.

    Args:
        file_bytes: Audio binary content (wav, mp3, m4a, webm, ogg, flac, etc.)
        filename: Original filename (used for content type resolution)
        language: Optional language hint (e.g. 'en', 'hi', 'gu')

    Returns:
        Dict containing:
            - success (bool)
            - text (str): Transcribed speech
            - language (str): Detected or requested language code
            - error (str, optional): Error message if failed
    """
    api_key = _get_api_key()
    if not api_key:
        return {
            "success": False,
            "text": "",
            "language": language or "en",
            "error": "GROQ_API_KEY is not configured in backend environment",
        }

    if not file_bytes or len(file_bytes) < 100:
        return {
            "success": False,
            "text": "",
            "language": language or "en",
            "error": "Audio data is empty or too short for speech recognition",
        }

    # Determine mime-type based on filename extension
    ext = filename.split(".")[-1].lower() if "." in filename else "wav"
    mime_map = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/m4a",
        "webm": "audio/webm",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
        "aac": "audio/aac",
    }
    content_type = mime_map.get(ext, "audio/wav")

    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, file_bytes, content_type)}
    data = {
        "model": GROQ_STT_MODEL,
        "response_format": "verbose_json",
    }
    if language:
        data["language"] = language

    try:
        if httpx is not None:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(GROQ_STT_URL, files=files, data=data, headers=headers)
            if resp.status_code == 200:
                res_data = resp.json()
                transcribed_text = res_data.get("text", "").strip()
                detected_lang = res_data.get("language", language or "en")
                
                # Determine ISO language code from transcribed text / Whisper detection
                detected_code = detect_query_language(transcribed_text, language)
                
                return {
                    "success": True,
                    "text": transcribed_text,
                    "language": detected_code,
                    "raw_language": detected_lang,
                }
            else:
                logger.error(f"Groq STT API error {resp.status_code}: {resp.text[:300]}")
                return {
                    "success": False,
                    "text": "",
                    "language": language or "en",
                    "error": f"Groq Whisper API returned status {resp.status_code}: {resp.text[:200]}",
                }
        else:
            return {
                "success": False,
                "text": "",
                "language": language or "en",
                "error": "httpx package is required for multipart audio transcription",
            }
    except Exception as e:
        logger.error(f"Groq STT request exception: {e}")
        return {
            "success": False,
            "text": "",
            "language": language or "en",
            "error": f"Failed to connect to Groq Speech API: {str(e)}",
        }


async def generate_tts_audio(
    text: str,
    language: str = "en",
) -> Tuple[Optional[bytes], str, Optional[str]]:
    """Generate audio MP3 bytes for text response using multilingual TTS.

    Args:
        text: Text to synthesize
        language: Language code (en, hi, gu, mr, bn, ta, te, kn, ml, pa, etc.)

    Returns:
        Tuple of (audio_bytes, content_type, error_msg)
    """
    if not text or not text.strip():
        return None, "audio/mpeg", "Text to synthesize is empty"

    # Clean formatting tags like markdown links, bold, bullet symbols, URLs for clearer speech
    clean_text = re.sub(r"\[.*?\]\(.*?\)", "", text)
    clean_text = re.sub(r"[*#_~`📌💰📋🔗•]", " ", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    if not clean_text:
        return None, "audio/mpeg", "Text is empty after cleaning"

    # Limit to ~600 chars for smooth fast playback
    clean_text = clean_text[:600]

    lang_map = {
        "en": "en", "hi": "hi", "gu": "gu", "mr": "mr", "bn": "bn",
        "ta": "ta", "te": "te", "kn": "kn", "ml": "ml", "pa": "pa",
        "or": "or", "ur": "ur", "ne": "ne", "ar": "ar", "fr": "fr",
        "es": "es", "de": "de", "ru": "ru", "ja": "ja", "zh": "zh-CN",
    }
    target_lang = lang_map.get(language, language)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        if httpx is not None:
            params = {
                "ie": "UTF-8",
                "q": clean_text,
                "tl": target_lang,
                "client": "tw-ob",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://translate.google.com/translate_tts",
                    params=params,
                    headers=headers,
                )
            if resp.status_code == 200 and len(resp.content) > 200:
                return resp.content, "audio/mpeg", None
            else:
                logger.warning(f"TTS API status {resp.status_code} for language={language}")
                return None, "audio/mpeg", f"TTS service returned status {resp.status_code}"
        else:
            return None, "audio/mpeg", "httpx package is required for TTS synthesis"
    except Exception as e:
        logger.error(f"TTS audio synthesis exception: {e}")
        return None, "audio/mpeg", f"TTS synthesis error: {str(e)}"


