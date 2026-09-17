"""Regression tests for language detection, portal answers, and fallback localization."""

import asyncio

import pytest

from app.services.language_service import language_registry
from app.services.groq_service import (
    _build_fallback_response,
    generate_grounded_chat_response,
)


def _detect(text, hint=None):
    return language_registry.detect_language(text, hint).code


@pytest.mark.parametrize(
    "text,hint,expected",
    [
        ("पीएम किसान क्या है?", None, "hi"),
        ("पीएम किसान क्या है?", "mr", "mr"),
        ("मला पीएम किसान योजनेची माहिती हवी आहे", None, "mr"),
        ("મને શિષ્યવૃત્તિ વિશે માહિતી આપો", "en", "gu"),
        ("PM Kisan ke liye kya documents chahiye?", "hi", "hi"),
        ("PM Kisan mate kya documents joie?", "gu", "gu"),
        ("PM Kisan sathi kay kagadpatra pahije?", "mr", "mr"),
        ("PM Kisan documents?", "gu", "en"),
        ("What is PM Kisan?", "hi", "en"),
        ("PM Kisan ke liye kya documents chahiye?", None, "en"),
    ],
)
def test_detect_language(text, hint, expected):
    assert _detect(text, hint) == expected


def test_nsp_is_not_described_as_maharashtra_portal():
    answer, citations, _ = asyncio.run(
        generate_grounded_chat_response("Tell me about NSP scholarship", chunks=[], language="en")
    )
    assert "National Scholarship Portal" in answer
    assert "Maharashtra" not in answer
    assert citations and citations[0]["url"] == "https://scholarships.gov.in/"


def test_mahadbt_still_described_as_maharashtra_portal():
    answer, citations, _ = asyncio.run(
        generate_grounded_chat_response("mahadt", chunks=[], language="en")
    )
    assert "MahaDBT" in answer
    assert "Maharashtra" in answer
    assert citations[0]["url"] == "https://www.mahadbt.maharashtra.gov.in/"


def test_portal_apply_steps_are_numbered_sequentially():
    answer, _, _ = asyncio.run(
        generate_grounded_chat_response("How do I apply on MahaDBT?", chunks=[], language="en")
    )
    for n in ("1.", "2.", "3.", "4."):
        assert n in answer


def test_clarification_is_not_marked_grounded():
    _, citations, is_grounded = asyncio.run(
        generate_grounded_chat_response("How do I apply?", chunks=[], language="en")
    )
    assert is_grounded is False
    assert citations == []


_CHUNK = {
    "scheme_name": "PM-KISAN",
    "section": "benefits",
    "content": "Benefits: Rs 6000 per year in three instalments.",
    "source_url": "https://pmkisan.gov.in/",
}


def test_fallback_is_localized_for_hindi():
    text = _build_fallback_response([_CHUNK], language_registry.get_spec("hi"))
    assert "अंग्रेज़ी" in text  # notice that details are in English
    assert "**लाभ**" in text
    assert "**Benefits**" not in text


def test_fallback_english_has_no_notice():
    text = _build_fallback_response([_CHUNK], language_registry.get_spec("en"))
    assert "**Benefits**" in text
    assert "ℹ️" not in text
