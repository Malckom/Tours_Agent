"""
Configuration for the Kenya Group Joining Safaris AI Agent (Safi).
Load environment variables before importing this module.
"""

import os
from datetime import date

# ─────────────────────────────────────────────
# API Keys (loaded from environment)
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
PINECONE_API_KEY: str = os.environ.get("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME: str = os.environ.get("PINECONE_INDEX_NAME", "kenya-safari-knowledge")

# Notification channel (Make.com webhook) for booking handoffs
NOTIFICATION_WEBHOOK_URL: str = os.environ.get("NOTIFICATION_WEBHOOK_URL", "")
NOTIFICATION_EMAIL: str = os.environ.get("NOTIFICATION_EMAIL", "bookings@groupjoiningsafaris.com")
WHATSAPP_API_TOKEN: str = os.environ.get("WHATSAPP_API_TOKEN", "")

# ─────────────────────────────────────────────
# Model Configuration
# ─────────────────────────────────────────────
CLAUDE_MODEL: str = "claude-sonnet-4-5"          # Swap to claude-opus-4 for higher quality
MAX_TOKENS: int = 2048                             # Max response length
TEMPERATURE: float = 0.3                           # Lower = more factual, consistent

# ─────────────────────────────────────────────
# Company Constants (never changes at runtime)
# ─────────────────────────────────────────────
COMPANY_NAME = "Kenya Group Joining Safaris"
COMPANY_LEGAL = "Kudu Hills Safaris Ltd"
COMPANY_PHONE = "+254 118 017 470"
COMPANY_WHATSAPP = "+254 118 017 470"
COMPANY_EMAIL_BOOKINGS = "bookings@groupjoiningsafaris.com"
COMPANY_EMAIL_GENERAL = "info@groupjoiningsafaris.com"
COMPANY_WEBSITE = "https://www.groupjoiningsafaris.com"
COMPANY_ADDRESS = "Veterans House, Moi Avenue, Nairobi, Kenya"

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_PROMPT_PATH = os.path.join(BASE_DIR, "agent", "system_prompt.txt")
PACKAGES_DATA_PATH = os.path.join(BASE_DIR, "data", "packages.json")
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "knowledge_base")

# ─────────────────────────────────────────────
# Season Context (injected into system prompt)
# ─────────────────────────────────────────────
def get_season_context() -> str:
    """Return a brief current season description for the system prompt."""
    today = date.today()
    month = today.month

    mara_fee = "USD 100/day (Jan–Jun rate)" if month <= 6 else "USD 200/day (Jul–Dec rate)"

    if month in (7, 8):
        migration = "Great Migration is currently IN the Masai Mara — peak river crossings. High demand, book early."
    elif month in (9, 10):
        migration = "Great Migration is still in the Masai Mara with good crossing activity. Peak season."
    elif month in (11, 12, 1, 2, 3):
        migration = "Migration herds are in Tanzania's Serengeti. Masai Mara has excellent resident game viewing year-round."
    else:  # Apr, May, Jun
        migration = "Migration herds are building in Tanzania, beginning to move north. Green/low season — good value."

    return f"Current Mara park fee: {mara_fee}. Migration status: {migration}"
