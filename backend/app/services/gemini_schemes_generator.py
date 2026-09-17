"""DEPRECATED — Gemini schemes generator migrated to Groq AI.

All functions and attributes are re-exported from groq_schemes_generator for backward compatibility.
"""

from app.services.groq_schemes_generator import *  # noqa: F401, F403

# Re-alias function name for legacy callers
generate_schemes_with_gemini = generate_schemes_with_groq
