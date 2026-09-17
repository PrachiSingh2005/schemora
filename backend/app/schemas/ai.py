from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    source_name: str
    url: str = ""  # Empty when no official URL available for this scheme
    last_verified_at: str = "2026-08-07"


class AIExplanationRequest(BaseModel):
    scheme_id: str
    language: str = Field("en", json_schema_extra={"example": "en"})


class AIExplanationResponse(BaseModel):
    scheme_id: str
    explanation: str
    citations: List[SourceCitation] = []


class RetrievedScheme(BaseModel):
    """A scheme chunk retrieved from the knowledge base for a RAG response."""
    scheme_id: Optional[str] = None
    scheme_name: str = ""
    section: str = ""
    similarity_score: float = 0.0
    jurisdiction: str = ""
    state: Optional[str] = None
    category: str = ""
    official_info_url: str = ""
    official_app_url: str = ""


class AIChatRequest(BaseModel):
    question: str = Field(
        ..., min_length=1,
        json_schema_extra={"example": "What documents are needed for CSSS scholarship?"}
    )
    scheme_id: Optional[str] = Field(None, json_schema_extra={"example": "sch-central-csss-001"})
    language: str = Field("en", json_schema_extra={"example": "en"})

    # Extended RAG fields
    profile_id: Optional[str] = Field(None, description="User profile ID for personalized eligibility context")
    state_filter: Optional[str] = Field(None, description="Restrict results to this state (e.g. Maharashtra)")
    category_filter: Optional[str] = Field(None, description="Restrict results to this category (e.g. Scholarship)")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None, description="Previous Q&A pairs for context"
    )
    conversation_context: Optional[Dict[str, str]] = Field(
        None,
        description="Context from previous turn for follow-up resolution. Contains: last_scheme, last_intent.",
        json_schema_extra={"example": {"last_scheme": "PM-KISAN", "last_intent": "SPECIFIC_SCHEME"}},
    )


class AIChatResponse(BaseModel):
    answer: str
    is_grounded: bool
    language: str = Field("en", description="Language code the answer is written in; use it for TTS playback")
    citations: List[SourceCitation] = []

    # Extended RAG response fields
    retrieved_schemes: List[RetrievedScheme] = []
    confidence_score: float = Field(0.0, description="Average similarity score of top retrieved chunks")
    suggested_questions: List[str] = Field([], description="Follow-up questions the user might want to ask")
    is_personalized: bool = Field(False, description="True if user profile was used to personalize the response")
    knowledge_base_used: bool = Field(True, description="True if RAG knowledge base was used")
    web_search_used: bool = Field(False, description="True if web search fallback was used")
    conversation_context: Optional[Dict[str, str]] = Field(
        None,
        description="Context for next turn. Frontend should cache and include in subsequent requests.",
    )



class KnowledgeBaseStatusResponse(BaseModel):
    """Status of the Schemora RAG knowledge base."""
    total_chunks: int
    semantic_chunks: int
    tfidf_chunks: int
    indexed_schemes: int
    total_documents: int
    embedding_model: str
    is_ready: bool


class KnowledgeBaseIndexResponse(BaseModel):
    """Result of a knowledge base indexing operation."""
    total_schemes: int
    indexed_schemes: int
    failed_schemes: List[Dict[str, str]] = []
    total_chunks: int
    semantic_chunks: int
    tfidf_chunks: int
    dataset_version: str
    message: str


class SpeechToTextResponse(BaseModel):
    """Response model for Speech-to-Text audio transcription."""
    text: str
    language: str = "en"
    raw_language: Optional[str] = None


class TextToSpeechRequest(BaseModel):
    """Request model for Text-to-Speech audio synthesis."""
    text: str = Field(..., min_length=1, description="Text to synthesize to speech")
    language: str = Field("en", description="Language code (e.g. en, hi, gu, mr, bn, ta, te)")


class AIRecommendationProfileInput(BaseModel):
    """Custom profile payload when user does not have a saved profile or wants to test specific criteria."""
    age: Optional[float] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    occupation: Optional[str] = None
    education_level: Optional[str] = None
    annual_family_income: Optional[float] = None
    social_category: Optional[str] = None
    language: str = Field("en", description="Language code (en, hi, gu, mr)")


class AIRecommendationItem(BaseModel):
    """A personalized scheme recommendation item."""
    scheme_id: str
    scheme_name: str
    match_type: str = Field("POTENTIAL_MATCH", description="One of: LIKELY_MATCH, POTENTIAL_MATCH, REQUIRES_VERIFICATION")
    confidence_score: float = Field(0.8, description="Deterministic match score between 0.0 and 1.0")
    match_reasons: List[str] = Field(default_factory=list, description="Reason tags e.g. ['Maharashtra', 'Farmer']")
    relevance_explanation: str = Field("", description="Grounded 1-2 sentence explanation of why this scheme matches")
    benefits_summary: str = Field("", description="Summary of financial or non-financial benefits")
    eligibility_summary: str = Field("", description="Summary of key eligibility requirements")
    provider: str = Field("", description="Department / Ministry / State provider")
    jurisdiction: str = Field("Central", description="Central or State")
    state: Optional[str] = None
    official_scheme_url: Optional[str] = None
    application_url: Optional[str] = None


class AIRecommendationResponse(BaseModel):
    """Response model for personalized AI recommendations."""
    recommendations: List[AIRecommendationItem] = Field(default_factory=list)
    total_matched: int = 0
    profile_summary: Dict[str, Any] = Field(default_factory=dict)
    has_profile: bool = True



