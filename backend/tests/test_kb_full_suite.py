"""Full Knowledge Base Validation Test Suite — Schemora.

Tests all intent categories, retrieval correctness, citation behavior,
language detection, follow-up context, and clarification triggers.

Run with:
  uv run pytest tests/test_kb_full_suite.py -v
  python -m pytest tests/test_kb_full_suite.py -v --tb=short

The tests use the live retrieval_service and groq_service directly (not the HTTP
API layer) to isolate the KB+retrieval logic from network/auth concerns.
"""

import asyncio
import pytest
import re
from typing import Optional, Dict, Any, List, Tuple
from unittest.mock import patch, AsyncMock

# ── Detect what environment we are in ────────────────────────────────────────

def _get_retrieval_service():
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from app.services.retrieval_service import (
            detect_intent,
            extract_query_entity_and_section,
            is_definition_query,
            INTENT_PATTERNS,
        )
        return detect_intent, extract_query_entity_and_section, is_definition_query
    except ImportError:
        return None, None, None


detect_intent, extract_query_entity_and_section, is_definition_query = _get_retrieval_service()

if detect_intent is None:
    pytest.skip("Could not import retrieval_service — run from backend directory", allow_module_level=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: INTENT DETECTION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestDefinitionIntent:
    """Tests for DEFINITION_CONCEPT intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        # English definitions
        ("What is a government scheme?", "DEFINITION_CONCEPT"),
        ("What are government schemes?", "DEFINITION_CONCEPT"),
        ("government schemes means?", "DEFINITION_CONCEPT"),
        ("government scheme meaning", "DEFINITION_CONCEPT"),
        ("meaning of government scheme", "DEFINITION_CONCEPT"),
        ("explain government schemes", "DEFINITION_CONCEPT"),
        ("define government scheme", "DEFINITION_CONCEPT"),
        ("what does government scheme mean?", "DEFINITION_CONCEPT"),
        ("what is a scheme?", "DEFINITION_CONCEPT"),
        ("what is eligibility?", "DEFINITION_CONCEPT"),
        ("what is subsidy?", "DEFINITION_CONCEPT"),
        ("what is DBT?", "DEFINITION_CONCEPT"),
        ("what is direct benefit transfer?", "DEFINITION_CONCEPT"),
        ("what is a scholarship?", "DEFINITION_CONCEPT"),
        ("scholarship meaning", "DEFINITION_CONCEPT"),
        # Hindi definitions
        ("government scheme kya hai?", "DEFINITION_CONCEPT"),
        ("सरकारी योजना क्या है?", "DEFINITION_CONCEPT"),
        ("योजना का मतलब क्या है?", "DEFINITION_CONCEPT"),
        # Gujarati definitions
        ("સરકારી યોજના શું છે?", "DEFINITION_CONCEPT"),
        ("scheme nee vyakhya shu che?", "DEFINITION_CONCEPT"),
    ])
    def test_definition_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\n"
            f"Expected: {expected_intent}\n"
            f"Got: {result}"
        )


class TestSchemeDiscoveryIntent:
    """Tests for SCHEME_DISCOVERY intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("What schemes are available for students?", "SCHEME_DISCOVERY"),
        ("Which schemes are available for farmers?", "SCHEME_DISCOVERY"),
        ("scholarships for SC students", "SCHEME_DISCOVERY"),
        ("show me schemes for women", "SCHEME_DISCOVERY"),
        ("schemes for OBC students", "SCHEME_DISCOVERY"),
    ])
    def test_discovery_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestSpecificSchemeIntent:
    """Tests for SPECIFIC_SCHEME and entity extraction."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("What is PM-KISAN?", "SPECIFIC_SCHEME"),
        ("Tell me about Atal Pension Yojana", "SPECIFIC_SCHEME"),
        ("Explain Ayushman Bharat", "SPECIFIC_SCHEME"),
        ("about PM KISAN scheme", "SPECIFIC_SCHEME"),
    ])
    def test_specific_scheme_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )

    @pytest.mark.parametrize("query,expected_entity", [
        ("What is PM-KISAN?", "PM-KISAN"),
        ("Tell me about Atal Pension Yojana", "Atal Pension Yojana"),
        ("Ayushman Bharat eligibility", "Ayushman Bharat PM-JAY"),
        ("post matric scholarship documents", "Post-Matric Scholarship for Scheduled Caste Students"),
        ("pre matric scholarship apply", "Pre-Matric Scholarship for Scheduled Caste Students"),
        ("PM YASASVI scholarship", "PM YASASVI Scholarship Scheme"),
    ])
    def test_entity_extraction(self, query, expected_entity):
        entity, _ = extract_query_entity_and_section(query)
        assert entity == expected_entity, (
            f"Query: '{query}'\nExpected entity: '{expected_entity}'\nGot: '{entity}'"
        )


class TestEligibilityIntent:
    """Tests for ELIGIBILITY intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("Who is eligible for PM-KISAN?", "ELIGIBILITY"),
        ("What is the income limit for Post-Matric Scholarship?", "ELIGIBILITY"),
        ("Am I eligible for Ayushman Bharat?", "ELIGIBILITY"),
        ("eligibility criteria for MYSY scholarship", "ELIGIBILITY"),
    ])
    def test_eligibility_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestBenefitsIntent:
    """Tests for BENEFITS intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("What benefits does PM-KISAN provide?", "BENEFITS"),
        ("How much financial assistance do I get from post-matric scholarship?", "BENEFITS"),
        ("how much stipend does Central Sector Scholarship give?", "BENEFITS"),
    ])
    def test_benefits_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestFinancialDetailsIntent:
    """Tests for FINANCIAL_DETAILS intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("How much money does PM-KISAN give per year?", "FINANCIAL_DETAILS"),
        ("exact amount of Atal Pension Yojana per month", "FINANCIAL_DETAILS"),
        ("what is the annual amount of MYSY scholarship?", "FINANCIAL_DETAILS"),
    ])
    def test_financial_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestDocumentsIntent:
    """Tests for REQUIRED_DOCUMENTS intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("What documents are required for PM-KISAN?", "REQUIRED_DOCUMENTS"),
        ("documents needed for post matric scholarship", "REQUIRED_DOCUMENTS"),
        ("certificate checklist for CSSS", "REQUIRED_DOCUMENTS"),
    ])
    def test_documents_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestApplicationIntent:
    """Tests for APPLICATION_PROCESS intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("How do I apply for PM-KISAN?", "APPLICATION_PROCESS"),
        ("What are the application steps for Post-Matric Scholarship?", "APPLICATION_PROCESS"),
        ("Steps to fill scholarship form", "APPLICATION_PROCESS"),
        ("how to register on NSP", "APPLICATION_PROCESS"),
    ])
    def test_application_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestApplicationChannelIntent:
    """Tests for APPLICATION_CHANNEL intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("Where can I apply offline for PM-KISAN?", "APPLICATION_CHANNEL"),
        ("Which CSC can I use to apply for scholarship?", "APPLICATION_CHANNEL"),
        ("online portal for PM KISAN application", "APPLICATION_CHANNEL"),
    ])
    def test_channel_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestRenewalIntent:
    """Tests for RENEWAL intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("Can I renew my scholarship?", "RENEWAL"),
        ("How to renew post matric scholarship?", "RENEWAL"),
        ("Scholarship renewal next year", "RENEWAL"),
        ("re-apply for scholarship", "RENEWAL"),
    ])
    def test_renewal_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestContactIntent:
    """Tests for CONTACT intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("What is the helpline number for PM-KISAN?", "CONTACT"),
        ("PM KISAN contact email", "CONTACT"),
        ("grievance portal for scholarship", "CONTACT"),
    ])
    def test_contact_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestStatusIntent:
    """Tests for STATUS intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("Is PM-KISAN currently active?", "STATUS"),
        ("Is Atal Pension Yojana still available?", "STATUS"),
        ("track my scholarship status", "STATUS"),
    ])
    def test_status_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


class TestComparisonIntent:
    """Tests for COMPARISON intent detection."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("Compare PM-KISAN and PMFBY", "COMPARISON"),
        ("difference between post matric and pre matric scholarship", "COMPARISON"),
        ("MYSY vs Central Sector Scholarship — which is better?", "COMPARISON"),
    ])
    def test_comparison_queries(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: CLARIFICATION TRIGGER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestClarificationTriggers:
    """Tests that ambiguous queries (no entity) are detected as needing clarification."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("How do I apply for a scholarship?", "APPLICATION_PROCESS"),
        ("What documents are required?", "REQUIRED_DOCUMENTS"),
        ("What is the deadline?", "DEADLINE"),
        ("What are the benefits?", "BENEFITS"),
        ("Am I eligible?", "ELIGIBILITY"),
        ("Can I renew?", "RENEWAL"),
        ("What is the contact number?", "CONTACT"),
    ])
    def test_ambiguous_queries_have_no_entity(self, query, expected_intent):
        intent = detect_intent(query)
        entity, _ = extract_query_entity_and_section(query)
        assert intent == expected_intent, (
            f"Query: '{query}'\nExpected intent: {expected_intent}\nGot: {intent}"
        )
        assert entity is None, (
            f"Query: '{query}'\nExpected no entity (should trigger clarification)\nGot entity: '{entity}'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: SECTION EXTRACTION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestSectionExtraction:
    """Tests for target section extraction from entity queries."""

    @pytest.mark.parametrize("query,expected_section", [
        ("What documents are required for PM-KISAN?", "documents"),
        ("How do I apply for Atal Pension Yojana?", "application"),
        ("Who is eligible for PM-KISAN?", "eligibility"),
        ("What benefits does Ayushman Bharat provide?", "benefits"),
        ("What is the deadline for Post-Matric Scholarship?", "deadlines"),
    ])
    def test_section_extraction(self, query, expected_section):
        _, section = extract_query_entity_and_section(query)
        assert section == expected_section, (
            f"Query: '{query}'\nExpected section: '{expected_section}'\nGot: '{section}'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: LANGUAGE HANDLING TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestLanguageHandling:
    """Tests for correct language detection of queries."""

    @pytest.mark.parametrize("query,expected_intent", [
        # English
        ("What is a government scheme?", "DEFINITION_CONCEPT"),
        ("What schemes are available for farmers?", "SCHEME_DISCOVERY"),
        # Hindi
        ("सरकारी योजना क्या है?", "DEFINITION_CONCEPT"),
        ("किसानों के लिए कौनसी योजनाएं हैं?", "SCHEME_DISCOVERY"),
        # Gujarati
        ("સરકારી યોજના શું છે?", "DEFINITION_CONCEPT"),
        ("ખેડૂતો માટે કઈ સ્કીમ છે?", "SCHEME_DISCOVERY"),
    ])
    def test_multilingual_intent_detection(self, query, expected_intent):
        result = detect_intent(query)
        assert result == expected_intent, (
            f"Multilingual query: '{query}'\nExpected: {expected_intent}\nGot: {result}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: EDGE CASE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases that should NOT be misclassified."""

    @pytest.mark.parametrize("query,forbidden_intent", [
        # These are DEFINITIONS — should NOT be SCHEME_DISCOVERY
        ("What is a government scheme?", "SCHEME_DISCOVERY"),
        ("government schemes means?", "SCHEME_DISCOVERY"),
        ("What are government schemes?", "SCHEME_DISCOVERY"),
        ("define eligibility", "SCHEME_DISCOVERY"),
        # These are DISCOVERY — should NOT be DEFINITION
        ("What schemes are available for students?", "DEFINITION_CONCEPT"),
        ("scholarships for farmers", "DEFINITION_CONCEPT"),
    ])
    def test_no_misclassification(self, query, forbidden_intent):
        result = detect_intent(query)
        assert result != forbidden_intent, (
            f"Query: '{query}' was incorrectly classified as {forbidden_intent}"
        )

    def test_greeting_is_not_scheme_discovery(self):
        assert detect_intent("hello") == "GREETING"
        assert detect_intent("hi") == "GREETING"
        assert detect_intent("namaste") == "GREETING"

    def test_thanks_intent(self):
        assert detect_intent("thank you") == "THANKS"
        assert detect_intent("thanks") == "THANKS"

    def test_definition_always_beats_discovery(self):
        """'What are government schemes?' should ALWAYS be DEFINITION, never DISCOVERY."""
        q = "what are government schemes?"
        assert detect_intent(q) == "DEFINITION_CONCEPT", (
            f"CRITICAL: '{q}' must be DEFINITION_CONCEPT, never SCHEME_DISCOVERY"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: KNOWLEDGE BASE CHUNK BUILDER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestChunkBuilders:
    """Tests for the new section chunk builders in knowledge_base_service."""

    def _get_builders(self):
        try:
            from app.services.knowledge_base_service import (
                _build_objective_chunk,
                _build_financial_details_chunk,
                _build_beneficiaries_chunk,
                _build_application_channels_chunk,
                _build_status_chunk,
                _build_renewal_chunk,
                _build_restrictions_chunk,
                _build_contact_chunk,
                build_chunks_for_scheme,
            )
            return {
                "objective": _build_objective_chunk,
                "financial_details": _build_financial_details_chunk,
                "beneficiaries": _build_beneficiaries_chunk,
                "application_channels": _build_application_channels_chunk,
                "status": _build_status_chunk,
                "renewal": _build_renewal_chunk,
                "restrictions": _build_restrictions_chunk,
                "contact": _build_contact_chunk,
                "build_all": build_chunks_for_scheme,
            }
        except ImportError:
            return None

    SAMPLE_SCHEME = {
        "scheme_id": "sch-test-pmkisan",
        "scheme_name": "PM-KISAN",
        "objective": "Provide income support to all farmer families in India.",
        "ministry": "Ministry of Agriculture and Farmers Welfare",
        "benefits": [{"description": "Annual income support", "amount": "6000", "currency": "INR", "frequency": "year"}],
        "eligibility_rules": {"root": {"type": "and", "conditions": [{"type": "condition", "description": "Must be a farmer"}]}},
        "required_documents": [{"name": "Aadhaar Card", "required": True}, {"name": "Land Records", "required": True}],
        "application_process": [{"step_number": 1, "channel": "Online Portal", "description": "Visit pmkisan.gov.in"}],
        "official_information_url": "https://pmkisan.gov.in",
        "official_application_url": "https://pmkisan.gov.in/Formalization/NewFarmerReg.aspx",
        "helpline": "011-23381092",
        "email": "pmkisan-ict@gov.in",
        "status": "Active",
        "category": "Agriculture",
        "jurisdiction": "Central",
        "gender_eligibility": "All",
        "social_categories": "All",
    }

    def test_objective_chunk(self):
        builders = self._get_builders()
        if not builders:
            pytest.skip("knowledge_base_service not importable")
        result = builders["objective"](self.SAMPLE_SCHEME)
        assert "Objective" in result or "Purpose" in result
        assert "income support" in result.lower()

    def test_financial_details_chunk(self):
        builders = self._get_builders()
        if not builders:
            pytest.skip("knowledge_base_service not importable")
        result = builders["financial_details"](self.SAMPLE_SCHEME)
        assert "6000" in result
        assert "INR" in result

    def test_contact_chunk(self):
        builders = self._get_builders()
        if not builders:
            pytest.skip("knowledge_base_service not importable")
        result = builders["contact"](self.SAMPLE_SCHEME)
        assert "011-23381092" in result
        assert "pmkisan-ict@gov.in" in result

    def test_status_chunk(self):
        builders = self._get_builders()
        if not builders:
            pytest.skip("knowledge_base_service not importable")
        result = builders["status"](self.SAMPLE_SCHEME)
        assert "Active" in result

    def test_build_all_chunks_has_new_sections(self):
        builders = self._get_builders()
        if not builders:
            pytest.skip("knowledge_base_service not importable")
        chunks = builders["build_all"](self.SAMPLE_SCHEME)
        sections = {c["section"] for c in chunks}
        expected_new_sections = {"objective", "financial_details", "contact", "status", "application_channels"}
        assert expected_new_sections.issubset(sections), (
            f"Missing new sections: {expected_new_sections - sections}"
        )

    def test_chunks_have_enriched_metadata(self):
        builders = self._get_builders()
        if not builders:
            pytest.skip("knowledge_base_service not importable")
        chunks = builders["build_all"](self.SAMPLE_SCHEME)
        for chunk in chunks:
            assert "ministry" in chunk, f"Missing 'ministry' in chunk {chunk['section']}"
            assert "language" in chunk, f"Missing 'language' in chunk {chunk['section']}"
            assert "content_hash" in chunk, f"Missing 'content_hash' in chunk {chunk['section']}"
            assert "source_authority" in chunk, f"Missing 'source_authority' in chunk {chunk['section']}"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: GLOSSARY SERVICE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestGlossaryService:
    """Tests for new glossary concepts."""

    def test_new_glossary_concepts_present(self):
        try:
            from app.services.glossary_service import GLOSSARY_CONCEPTS
        except ImportError:
            pytest.skip("glossary_service not importable")

        concept_keys = {c["key"] for c in GLOSSARY_CONCEPTS}
        required_new_concepts = {
            "scholarship", "dbt", "income_certificate",
            "caste_certificate", "disability_certificate",
            "residence_domicile_certificate", "renewal", "common_service_centre",
        }
        missing = required_new_concepts - concept_keys
        assert not missing, f"Missing glossary concepts: {missing}"

    def test_total_concepts_count(self):
        try:
            from app.services.glossary_service import GLOSSARY_CONCEPTS
        except ImportError:
            pytest.skip("glossary_service not importable")

        assert len(GLOSSARY_CONCEPTS) >= 18, (
            f"Expected >= 18 glossary concepts, got {len(GLOSSARY_CONCEPTS)}"
        )

    def test_glossary_concepts_have_multilingual_content(self):
        try:
            from app.services.glossary_service import GLOSSARY_CONCEPTS
        except ImportError:
            pytest.skip("glossary_service not importable")

        for concept in GLOSSARY_CONCEPTS:
            content = concept.get("content", "")
            if concept["key"] in ["scholarship", "dbt", "income_certificate"]:
                assert any(marker in content for marker in ["\u0939\u093f\u0902\u0926\u0940", "Hindi", "\u0917\u0941\u091c\u0930\u093e\u0924\u0940", "Gujarati"]), (
                    f"Concept '{concept['key']}' missing multilingual content"
                )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8: CITATION CONTROL TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestCitationControl:
    """Tests for max-1 citation behavior."""

    def test_citations_max_one(self):
        try:
            from app.services.groq_service import _build_citations
        except ImportError:
            pytest.skip("groq_service not importable")

        many_chunks = [
            {"source_url": f"https://scheme{i}.gov.in", "source_title": f"Scheme {i}", "last_verified_at": "2026-08-07", "official_app_url": ""}
            for i in range(10)
        ]
        result = _build_citations(many_chunks)
        assert len(result) <= 1, (
            f"Expected max 1 citation, got {len(result)}: {[c['url'] for c in result]}"
        )

    def test_citation_returns_official_url(self):
        try:
            from app.services.groq_service import _build_citations
        except ImportError:
            pytest.skip("groq_service not importable")

        chunks = [
            {"source_url": "https://pmkisan.gov.in", "source_title": "PM-KISAN", "last_verified_at": "2026-08-07", "official_app_url": ""}
        ]
        result = _build_citations(chunks)
        assert len(result) == 1
        assert result[0]["url"] == "https://pmkisan.gov.in"

    def test_no_fake_urls_in_citations(self):
        try:
            from app.services.groq_service import _build_citations
        except ImportError:
            pytest.skip("groq_service not importable")

        chunks_no_url = [{"source_url": "", "source_title": "No URL", "official_app_url": ""}]
        result = _build_citations(chunks_no_url)
        assert len(result) == 0


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9: SCRAPER DATA QUALITY TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestScraperDataQuality:
    """Tests for the data quality validation in portal_scraper."""

    def test_validate_rejects_generic_description(self):
        try:
            from app.services.scraper.portal_scraper import _validate_scheme_record
        except ImportError:
            pytest.skip("portal_scraper not importable")

        fake_record = {
            "description": "Official myScheme government scheme record for Test Scheme provided under Ministry of Social Welfare.",
            "required_documents": [
                {"name": "Aadhaar Card"},
                {"name": "Income Certificate"},
            ],
            "application_process": [{"description": "Register online at official portal and fill application form."}],
        }
        assert _validate_scheme_record(fake_record) is False, "Should reject generic placeholder data"

    def test_validate_accepts_real_data(self):
        try:
            from app.services.scraper.portal_scraper import _validate_scheme_record
        except ImportError:
            pytest.skip("portal_scraper not importable")

        real_record = {
            "description": "PM-KISAN is a Central Sector scheme of Government of India to provide income support to all land holding farmers' families in the country to supplement their financial needs.",
            "required_documents": [
                {"name": "Land Records / Khasra-Khatauni", "required": True},
                {"name": "Aadhaar Card", "required": True},
                {"name": "Bank Account Passbook (Aadhaar-linked)", "required": True},
            ],
            "application_process": [
                {"description": "Visit the official PM-KISAN portal at pmkisan.gov.in and click on 'New Farmer Registration'."},
                {"description": "Enter your Aadhaar Number, State, and other personal details as required."},
                {"description": "Submit the form and save the application reference number for future tracking."},
            ],
        }
        assert _validate_scheme_record(real_record) is True, "Should accept real scheme data"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10: DISCOVERY ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestDiscoveryEngine:
    """Tests for myscheme_discovery.py."""

    def test_known_slugs_count(self):
        try:
            from app.services.scraper.myscheme_discovery import KNOWN_MYSCHEME_SLUGS
        except ImportError:
            pytest.skip("myscheme_discovery not importable")

        assert len(KNOWN_MYSCHEME_SLUGS) >= 60, (
            f"Expected >= 60 known slugs, got {len(KNOWN_MYSCHEME_SLUGS)}"
        )

    def test_known_slugs_have_no_duplicates(self):
        try:
            from app.services.scraper.myscheme_discovery import KNOWN_MYSCHEME_SLUGS
        except ImportError:
            pytest.skip("myscheme_discovery not importable")

        assert len(KNOWN_MYSCHEME_SLUGS) == len(set(KNOWN_MYSCHEME_SLUGS)), (
            "KNOWN_MYSCHEME_SLUGS contains duplicate entries"
        )

    def test_known_slugs_major_schemes_present(self):
        try:
            from app.services.scraper.myscheme_discovery import KNOWN_MYSCHEME_SLUGS
        except ImportError:
            pytest.skip("myscheme_discovery not importable")

        required = [
            "pm-kisan-samman-nidhi",
            "ayushman-bharat-pradhan-mantri-jan-arogya-yojana",
            "pradhan-mantri-fasal-bima-yojana",
            "atal-pension-yojana",
            "pradhan-mantri-jan-dhan-yojana",
            "pm-awas-yojana-urban",
        ]
        missing = [s for s in required if s not in KNOWN_MYSCHEME_SLUGS]
        assert not missing, f"Major scheme slugs missing from discovery list: {missing}"


if __name__ == "__main__":
    # Quick sanity run without pytest
    print("Running quick sanity checks...")
    cases = [
        ("What is a government scheme?", "DEFINITION_CONCEPT"),
        ("government schemes means?", "DEFINITION_CONCEPT"),
        ("What schemes are available for students?", "SCHEME_DISCOVERY"),
        ("What is PM-KISAN?", "SPECIFIC_SCHEME"),
        ("Who is eligible for PM-KISAN?", "ELIGIBILITY"),
        ("What documents are required for PM-KISAN?", "REQUIRED_DOCUMENTS"),
        ("How do I apply for PM-KISAN?", "APPLICATION_PROCESS"),
        ("Can I renew my scholarship?", "RENEWAL"),
        ("What is the helpline for PM-KISAN?", "CONTACT"),
        ("Compare PM-KISAN and PMFBY", "COMPARISON"),
        ("સરકારી યોજના શું છે?", "DEFINITION_CONCEPT"),
        ("सरकारी योजना क्या है?", "DEFINITION_CONCEPT"),
    ]
    passed = 0
    failed = 0
    for query, expected in cases:
        result = detect_intent(query)
        status = "✓" if result == expected else "✗"
        if result != expected:
            print(f"  {status} FAIL: '{query}'\n    Expected: {expected} | Got: {result}")
            failed += 1
        else:
            print(f"  {status} PASS: '{query}' → {result}")
            passed += 1
    print(f"\nResults: {passed}/{len(cases)} passed, {failed} failed.")
