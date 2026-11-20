"""Default values for the business rules (SRS sections 4 and 5).

These are defaults only. config.py can override the tunable ones from .env, and the
container passes the final values into use cases and agent steps.
"""

from typing import Final

# Router (FR-AGT-03)
ROUTER_CONFIDENCE_THRESHOLD: Final = 0.7

# Retrieval (FR-AGT-05, FR-AGT-07)
TOP_K: Final = 5
RETRIEVAL_MIN_SCORE: Final = 0.80
MIN_FILTERED_RESULTS: Final = 2  # fewer than this above the score -> also search without the filter
MAX_RETRIEVAL_RETRIES: Final = 2

# Answer shape (FR-AGT-08, FR-CALL-03, SRS 3.2)
MAX_SPEECH_WORDS: Final = 45
MAX_SMS_CHARS: Final = 300
HISTORY_TURNS_FOR_PROMPT: Final = 3
HISTORY_MESSAGES_TO_LOAD: Final = 6

# Voice call (FR-CALL-04, 06, 10)
MAX_TURNS_PER_CALL: Final = 6
MAX_SILENT_REPROMPTS: Final = 1
VOICE_BUDGET_SECONDS: Final = 8

# Call-back (FR-CALL-07)
CALLBACK_COOLDOWN_SECONDS: Final = 60

# Cache (FR-AGT-15)
CACHE_TTL_HOURS: Final = 24
