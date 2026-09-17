import unittest
import asyncio
from app.services.groq_service import (
    is_out_of_scope,
    generate_grounded_explanation,
    generate_grounded_chat_response,
)


class TestGroqService(unittest.TestCase):

    def test_out_of_scope_query_detection(self):
        self.assertTrue(is_out_of_scope("Who won the cricket match yesterday?"))
        self.assertTrue(is_out_of_scope("What is the weather forecast for tomorrow?"))
        self.assertFalse(is_out_of_scope("What is the income eligibility for CSSS scholarship?"))

    def test_generate_grounded_explanation_formatting(self):
        sources = [{"source_name": "NSP Portal", "url": "https://scholarships.gov.in", "last_verified_at": "2026-08-07"}]
        matched = [{"field_name": "state"}]

        explanation, citations = generate_grounded_explanation(
            scheme_title="CSSS Scholarship",
            status="RuleMatched",
            matched_rules=matched,
            unresolved_rules=[],
            sources=sources,
            language="en",
        )

        self.assertIn("CSSS Scholarship", explanation)
        self.assertIn("satisfy all mandatory criteria", explanation)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["source_name"], "NSP Portal")

    def test_groq_grounded_chat_greeting(self):
        answer, citations, is_grounded = asyncio.run(
            generate_grounded_chat_response(
                query="Hello",
                chunks=[],
                language="en",
            )
        )
        self.assertIn("Schemora AI Assistant", answer)
        self.assertTrue(is_grounded)

    def test_groq_grounded_chat_out_of_scope(self):
        answer, citations, is_grounded = asyncio.run(
            generate_grounded_chat_response(
                query="What is the weather today?",
                chunks=[],
                language="en",
            )
        )
        self.assertFalse(is_grounded)
        self.assertTrue("Government Scheme Assistant" in answer or "scheme" in answer.lower())

    def test_transcribe_audio_empty_bytes_handling(self):
        from app.services.groq_service import transcribe_audio_with_groq
        res = asyncio.run(transcribe_audio_with_groq(b"", filename="empty.wav"))
        self.assertFalse(res["success"])
        self.assertIn("empty", res["error"].lower())

    def test_format_web_results_as_chunks(self):
        from app.services.web_search_service import format_web_results_as_chunks
        dummy = [{"title": "PM Kisan Portal", "url": "https://pmkisan.gov.in", "snippet": "PM Kisan official guidelines"}]
        chunks = format_web_results_as_chunks(dummy)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["scheme_name"], "PM Kisan Portal")
        self.assertTrue(chunks[0]["is_web_search"])

    def test_evaluate_chunk_relevance_thresholds(self):
        from app.services.groq_service import evaluate_chunk_relevance
        relevant_chunks = [{"scheme_name": "CSSS Scholarship", "content": "Documents required for scholarship", "similarity_score": 0.85}]
        is_rel, score = evaluate_chunk_relevance("What documents for CSSS?", relevant_chunks)
        self.assertTrue(is_rel)
        self.assertGreaterEqual(score, 0.5)

        is_empty_rel, empty_score = evaluate_chunk_relevance("What documents for CSSS?", [])
        self.assertFalse(is_empty_rel)
        self.assertEqual(empty_score, 0.0)


if __name__ == "__main__":
    unittest.main()




