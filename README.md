# Kenya Group Joining Safaris — Safi AI Agent

**Safi** is the AI safari consultant for [Kenya Group Joining Safaris](https://www.groupjoiningsafaris.com)
(operated by Kudu Hills Safaris Ltd, Nairobi, Kenya).

> *Safi* means "pure" and "clear" in Swahili — reflecting the untouched wilderness
> experiences the company delivers.

---

## Project Structure

```
Tours_Agent/
├── agent/
│   ├── agent.py           # Main agent class + CLI runner
│   ├── tools.py           # Tool function implementations
│   ├── tool_schemas.py    # Anthropic tool JSON schemas
│   ├── config.py          # Config, paths, season context
│   ├── system_prompt.txt  # Master system prompt (Safi's identity)
│   └── __init__.py
├── knowledge_base/
│   ├── company_info.md
│   ├── packages/
│   │   ├── nairobi_national_park.md
│   │   └── masai_mara_3day.md
│   ├── accommodations/
│   │   └── masai_mara_lodges.md  # All 9 camps with seasonal rates
│   ├── policies/
│   │   └── booking_policies.md   # DRAFT — fill in before launch
│   └── faqs/
│       └── common_questions.md   # 35 Q&As
├── data/
│   └── packages.json      # Structured pricing data (source of truth)
├── scripts/
│   ├── test_agent.py           # Smoke test 3 realistic scenarios
│   └── ingest_knowledge_base.py # Phase 2: embed KB into Pinecone
├── AGENT_BLUEPRINT.md     # Full system design blueprint
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Add your Anthropic API key to .env:
# ANTHROPIC_API_KEY=sk-ant-...
```

Get your key at [console.anthropic.com](https://console.anthropic.com).

### 3. Chat with Safi (CLI)

```bash
python -m agent.agent
```

### 4. Run smoke tests

```bash
python scripts/test_agent.py
```

---

## How It Works

```
Customer message
      │
      ▼
SafiAgent.chat()
      │
      ▼
Claude API + system_prompt + tools + conversation history
      │
      ├── tool_use → execute tool(s) → results → loop back
      └── end_turn → return text response to customer
```

### Tools

| Tool | Purpose |
|---|---|
| `search_packages` | Find packages by criteria |
| `get_package_details` | Full itinerary and inclusions |
| `calculate_pricing` | Live price calculation |
| `get_accommodation_options` | List Mara camps by category |
| `get_seasonal_context` | Migration status and park fees for a date |
| `create_lead` | Log booking intent |
| `notify_booking_team` | Handoff notification to team |
| `escalate_to_human` | Route to human agent |

---

## Pricing Structure

**Nairobi NP:** Transport ($36–$90/pp based on vehicle occupancy) + park fees ($87 adult / $47 child)

**Masai Mara 3-day:** Transport ($45/pp/day × 3 days = **$135/person**) + park fees ($100 Jan–Jun / $200 Jul–Dec, adult/day × 2 game drive days) + 2 nights Full Board accommodation at chosen camp

All prices USD, non-resident rates. See `data/packages.json` for full detail.

---

## Week 1 Action Items (Before Launch)

- [ ] Fill in cancellation policy in `knowledge_base/policies/booking_policies.md`
- [ ] Confirm FAQ answers marked `[TO BE CONFIRMED]`
- [ ] Add Mara transport pricing tiers to `data/packages.json`
- [ ] Set `NOTIFICATION_WEBHOOK_URL` in `.env` for booking alerts
- [ ] Define human escalation contacts in `agent/config.py`

---

## Business Rules (Enforced in System Prompt)

1. Never quote prices from memory — always call `calculate_pricing`
2. Never confirm bookings — only hand off via `notify_booking_team`
3. Never collect card numbers in chat
4. Never promise specific animal sightings
5. Never guess uncertain policy details — escalate
6. Escalate immediately for emergencies and legal complaints

---

## Contact

**Kenya Group Joining Safaris / Kudu Hills Safaris Ltd**  
WhatsApp/Phone: +254 118 017 470 | bookings@groupjoiningsafaris.com  
[www.groupjoiningsafaris.com](https://www.groupjoiningsafaris.com) | Veterans House, Moi Avenue, Nairobi
