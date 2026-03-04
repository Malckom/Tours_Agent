"""
Tool implementations for the Kenya Group Joining Safaris AI Agent (Safi).

Each function:
  - Corresponds to a tool the Claude model may call
  - Returns a dict that is serialised as the tool_result message
  - Raises ToolError on hard failures (agent will surface a friendly message)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any

import requests  # pip install requests  (used for notification webhook)

from agent.config import (
    COMPANY_EMAIL_BOOKINGS,
    COMPANY_PHONE,
    COMPANY_WHATSAPP,
    NOTIFICATION_EMAIL,
    NOTIFICATION_WEBHOOK_URL,
    PACKAGES_DATA_PATH,
    WHATSAPP_API_TOKEN,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Load static package data once at import time
# ─────────────────────────────────────────────────────────────
with open(PACKAGES_DATA_PATH, "r") as _f:
    _PACKAGES: dict = json.load(_f)


class ToolError(Exception):
    """Raised when a tool cannot complete its operation."""


# ─────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────

def _get_mara_season(travel_date: date) -> str:
    """Return season key for a given date based on Masai Mara calendar."""
    month = travel_date.month
    day = travel_date.day

    # Easter 2026: Apr 3–6
    if travel_date.month == 4 and 3 <= travel_date.day <= 6:
        return "easter"
    # Christmas: Dec 22–26
    if travel_date.month == 12 and 22 <= travel_date.day <= 26:
        return "christmas"
    # New Year: Dec 31 – Jan 2
    if (travel_date.month == 12 and travel_date.day == 31) or (
        travel_date.month == 1 and travel_date.day <= 2
    ):
        return "new_year"

    # Peak migration months
    if month in (7, 8):
        return "peak"
    if month in (9, 10):
        return "high"
    if month in (4, 5):
        return "low"
    # Jan, Feb, Mar, Jun, Nov, Dec (non-festive)
    return "regular"


def _mara_park_fee(travel_date: date) -> int:
    """Return adult non-resident Mara park fee for a given date."""
    return 200 if travel_date.month >= 7 else 100


def _nnp_total(pax: list[dict], group_size_in_vehicle: int) -> dict:
    """
    Calculate Nairobi National Park half-day total.
    pax: list of {"type": "adult"|"child", "count": N}
    group_size_in_vehicle: total passengers (determines transport tier)
    """
    transport_tiers = {1: 90, 2: 90, 3: 68, 4: 54, 5: 45, 6: 36}
    g = min(max(group_size_in_vehicle, 1), 6)
    transport_pp = transport_tiers.get(g, 36)

    park_fee_adult = _PACKAGES["packages"]["NNP-HALF-DAY"]["park_fees_usd_2026"][
        "non_resident_adult"
    ]
    park_fee_child = _PACKAGES["packages"]["NNP-HALF-DAY"]["park_fees_usd_2026"][
        "non_resident_child"
    ]

    total_transport = 0
    total_park = 0
    total_pax = 0

    for p in pax:
        count = p.get("count", 1)
        total_pax += count
        total_transport += transport_pp * count
        if p.get("type") == "child":
            total_park += park_fee_child * count
        else:
            total_park += park_fee_adult * count

    return {
        "transport_per_person_usd": transport_pp,
        "transport_total_usd": total_transport,
        "park_fees_total_usd": total_park,
        "grand_total_usd": total_transport + total_park,
        "total_passengers": total_pax,
        "breakdown": f"Transport: ${total_transport} ({total_pax} pax × ${transport_pp}) + Park fees: ${total_park}",
    }


def _get_accommodation_rate(
    accommodation_id: str, travel_date: date, room_type: str
) -> float | None:
    """Look up accommodation nightly rate for the given date and room type."""
    rooms = _PACKAGES["packages"]["MARA-3DAY-2N"]["accommodation_options"]
    acc = next((a for a in rooms if a["id"] == accommodation_id), None)
    if not acc:
        return None

    season = _get_mara_season(travel_date)
    rates = acc.get("seasonal_rates_usd_per_person_per_night", {})

    # Search season keys in priority order
    for key in [season, "peak", "high", "regular", "low"]:
        if key in rates:
            rate = rates[key].get(room_type)
            if rate is not None:
                return float(rate)
    return None


# ─────────────────────────────────────────────────────────────
# Tool: search_packages
# ─────────────────────────────────────────────────────────────

def search_packages(
    destinations: list[str] | None = None,
    budget_per_person_usd: float | None = None,
    accommodation_level: str | None = None,
    duration_days: int | None = None,
) -> dict:
    """
    Return a list of available packages matching the search criteria.
    Currently returns all packages (expand as inventory grows).
    """
    packages = _PACKAGES.get("packages", {})
    results = []

    for pkg_id, pkg in packages.items():
        results.append(
            {
                "id": pkg_id,
                "name": pkg["name"],
                "destination": pkg.get("destination", "Kenya"),
                "duration": pkg.get("duration_description"),
                "meal_plan": pkg.get("meal_plan"),
                "guaranteed_departure": pkg.get("guaranteed_departure", True),
                "max_group_size": pkg.get("max_group_size"),
            }
        )

    return {"packages": results, "total": len(results)}


# ─────────────────────────────────────────────────────────────
# Tool: get_package_details
# ─────────────────────────────────────────────────────────────

def get_package_details(package_id: str) -> dict:
    """Return the full details for a single package."""
    pkg = _PACKAGES["packages"].get(package_id)
    if not pkg:
        raise ToolError(f"Package '{package_id}' not found.")
    return {"package": pkg}


# ─────────────────────────────────────────────────────────────
# Tool: calculate_pricing
# ─────────────────────────────────────────────────────────────

def calculate_pricing(
    package_id: str,
    travel_date_str: str,
    pax: list[dict],
    accommodation_id: str | None = None,
    room_type: str = "double",
    nights: int | None = None,
    group_size_in_vehicle: int | None = None,
    include_park_fees: bool = True,
    addons: list[str] | None = None,
) -> dict:
    """
    Calculate the total price for a booking.

    pax: list of dicts, e.g. [{"type": "adult", "count": 2}, {"type": "child", "count": 1}]
    room_type: "single" | "double" | "triple"
    addons: list of addon keys, e.g. ["giraffe_centre", "david_sheldrick_elephant_orphanage"]
    """
    try:
        travel_date = datetime.strptime(travel_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ToolError(
            f"Invalid date format '{travel_date_str}'. Use YYYY-MM-DD."
        )

    pkg = _PACKAGES["packages"].get(package_id)
    if not pkg:
        raise ToolError(f"Package '{package_id}' not found.")

    total_pax_count = sum(p.get("count", 1) for p in pax)
    vehicle_size = group_size_in_vehicle or total_pax_count
    result: dict[str, Any] = {
        "package": pkg["name"],
        "travel_date": travel_date_str,
        "pax_breakdown": pax,
        "total_passengers": total_pax_count,
        "room_type": room_type,
        "currency": "USD",
        "line_items": {},
        "notes": [],
    }

    if package_id == "NNP-HALF-DAY":
        pricing = _nnp_total(pax, vehicle_size)
        result["line_items"]["transport"] = pricing["transport_total_usd"]
        if include_park_fees:
            result["line_items"]["park_fees"] = pricing["park_fees_total_usd"]
        result["notes"].append(
            f"Transport rate: USD {pricing['transport_per_person_usd']}/person "
            f"(based on {vehicle_size} passengers in vehicle)"
        )

        # Add-ons
        if addons:
            addon_defs = pkg.get("optional_addons", {})
            for addon_key in addons:
                addon = addon_defs.get(addon_key)
                if addon:
                    addon_cost = addon["price_usd"] * total_pax_count
                    result["line_items"][addon["name"]] = addon_cost
                    if addon_key == "david_sheldrick_elephant_orphanage":
                        result["notes"].append(
                            "David Sheldrick is open 11:00–12:00 only — only available with morning departure."
                        )

    elif package_id == "MARA-3DAY-2N":
        num_nights = nights or 2
        # Transport
        transport_pp_day = pkg["transport_rate_usd"]["per_person_per_day"]
        transport_total = transport_pp_day * 3 * total_pax_count
        result["line_items"]["transport_3_days"] = transport_total

        # Park fees (2 full game drive days as default)
        if include_park_fees:
            adult_fee = _mara_park_fee(travel_date)
            child_fee = 50  # fixed all year
            park_total = 0
            for p in pax:
                count = p.get("count", 1)
                if p.get("type") == "child":
                    park_total += child_fee * 2 * count  # 2 game drive days
                else:
                    park_total += adult_fee * 2 * count
            result["line_items"]["park_fees_2_days"] = park_total
            result["notes"].append(
                f"Masai Mara park fee: USD {adult_fee}/adult/day ({travel_date.strftime('%b %Y')} rate)"
            )

        # Accommodation
        if accommodation_id:
            acc_rooms = pkg.get("accommodation_options", [])
            acc = next((a for a in acc_rooms if a["id"] == accommodation_id), None)
            if not acc:
                result["notes"].append(
                    f"Accommodation '{accommodation_id}' not found — remove this ID and try again."
                )
            else:
                nightly_rate = _get_accommodation_rate(
                    accommodation_id, travel_date, room_type
                )
                if nightly_rate is None:
                    result["notes"].append(
                        f"Rate for {room_type} room at {acc['name']} not found for this season — contact us."
                    )
                else:
                    acc_total = nightly_rate * num_nights * total_pax_count
                    result["line_items"][
                        f"accommodation_{acc['name']}_{num_nights}n_{room_type}"
                    ] = acc_total
                    result["notes"].append(
                        f"{acc['name']} ({acc['category']}): USD {nightly_rate}/person/night × {num_nights} nights × {total_pax_count} pax"
                    )
        else:
            result["notes"].append(
                "Accommodation not selected — add accommodation_id to get a full quote."
            )
    else:
        raise ToolError(f"Pricing logic not yet implemented for package '{package_id}'.")

    result["subtotal_usd"] = sum(result["line_items"].values())
    result["grand_total_usd"] = result["subtotal_usd"]

    result["notes"].append(
        "All prices are for non-residents in USD. Resident rates available on request."
    )
    result["notes"].append(
        "Tips, drinks at camp, and personal expenses are not included."
    )

    return result


# ─────────────────────────────────────────────────────────────
# Tool: get_accommodation_options
# ─────────────────────────────────────────────────────────────

def get_accommodation_options(
    package_id: str = "MARA-3DAY-2N",
    category: str | None = None,
) -> dict:
    """Return accommodation options for the Masai Mara package, optionally filtered by category."""
    pkg = _PACKAGES["packages"].get(package_id)
    if not pkg:
        raise ToolError(f"Package '{package_id}' not found.")

    options = pkg.get("accommodation_options", [])
    if category:
        options = [o for o in options if o.get("category", "").lower() == category.lower()]

    return {
        "package": pkg["name"],
        "accommodation_options": [
            {
                "id": o["id"],
                "name": o["name"],
                "category": o.get("category"),
                "meal_plan": o.get("meal_plan"),
                "aliases": o.get("aliases", []),
            }
            for o in options
        ],
        "total": len(options),
    }


# ─────────────────────────────────────────────────────────────
# Tool: get_seasonal_context
# ─────────────────────────────────────────────────────────────

def get_seasonal_context(travel_date_str: str | None = None) -> dict:
    """Return season and migration information for a given date (or today)."""
    if travel_date_str:
        try:
            travel_date = datetime.strptime(travel_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ToolError(f"Invalid date '{travel_date_str}'. Use YYYY-MM-DD.")
    else:
        travel_date = date.today()

    month = travel_date.month
    mara_fee = _mara_park_fee(travel_date)
    season = _get_mara_season(travel_date)

    migration_status = {
        1: "Migration in Tanzania (Serengeti calving season Jan–Feb). Excellent resident game in Mara.",
        2: "Migration in Tanzania (Serengeti). Good low-season value in Mara.",
        3: "Migration in Tanzania, beginning northward movement. Good value season.",
        4: "Long rains begin. Migration moving north. Lush green Mara. Fewer crowds.",
        5: "Long rains (can be heavy). Migration moving north. Budget-friendly.",
        6: "Migration crossing into Mara from late June. Exciting build-up.",
        7: "Great Migration arrives in Mara. River crossings beginning. Peak season.",
        8: "Peak of Great Migration — dramatic Mara River crossings. Highest demand.",
        9: "Migration river crossings continue (can extend to Oct). Spectacular season.",
        10: "Migration herds still present, beginning return south. Good sightings.",
        11: "Short rains. Migration heading south. Excellent resident game, fewer crowds.",
        12: "Migration in Tanzania. Festive season surcharges at properties.",
    }.get(month, "Contact us for current migration status.")

    return {
        "travel_date": str(travel_date),
        "month_name": travel_date.strftime("%B %Y"),
        "mara_season": season,
        "mara_adult_park_fee_usd": mara_fee,
        "migration_status": migration_status,
        "nnp_park_fee_adult_usd": 87,
        "nnp_park_fee_child_usd": 47,
    }


# ─────────────────────────────────────────────────────────────
# Tool: create_lead
# ─────────────────────────────────────────────────────────────

def create_lead(
    first_name: str,
    last_name: str,
    email: str,
    phone: str | None = None,
    nationality: str | None = None,
    package_id: str | None = None,
    travel_date: str | None = None,
    pax_count: int | None = None,
    accommodation_id: str | None = None,
    room_type: str | None = None,
    notes: str | None = None,
) -> dict:
    """
    Log a customer lead (booking intent) to the console/log.
    In production: replace with CRM API call (HubSpot, Zoho, etc.)
    """
    lead = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "name": f"{first_name} {last_name}",
        "email": email,
        "phone": phone,
        "nationality": nationality,
        "package_id": package_id,
        "travel_date": travel_date,
        "pax_count": pax_count,
        "accommodation_id": accommodation_id,
        "room_type": room_type,
        "notes": notes,
        "source": "safi_chatbot",
    }
    logger.info("LEAD CREATED: %s", json.dumps(lead, indent=2))

    # TODO: Replace with actual CRM integration
    # e.g. requests.post(CRM_API_URL, json=lead, headers={"Authorization": f"Bearer {CRM_TOKEN}"})

    return {
        "success": True,
        "message": "Lead recorded. Booking team will follow up.",
        "lead_id": f"LEAD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
    }


# ─────────────────────────────────────────────────────────────
# Tool: notify_booking_team
# ─────────────────────────────────────────────────────────────

def notify_booking_team(
    customer_name: str,
    customer_email: str,
    customer_phone: str | None,
    package_id: str,
    travel_date: str,
    pax_details: str,
    accommodation_id: str | None,
    room_type: str | None,
    total_quoted_usd: float | None,
    conversation_summary: str,
    priority: str = "normal",
) -> dict:
    """
    Send a booking handoff notification to the booking team.
    In Phase 1: sends to email or webhook. In Phase 2: creates booking in system.
    """
    pkg_name = _PACKAGES["packages"].get(package_id, {}).get("name", package_id)

    message = f"""
🦁 NEW SAFARI BOOKING REQUEST — {priority.upper()} PRIORITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Customer: {customer_name}
Email: {customer_email}
Phone/WhatsApp: {customer_phone or 'Not provided'}

Package: {pkg_name} ({package_id})
Travel Date: {travel_date}
Passengers: {pax_details}
Accommodation: {accommodation_id or 'Not selected'} ({room_type or 'Not specified'} room)
Price Quoted: USD {total_quoted_usd or 'Not yet calculated'}

Summary:
{conversation_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Action Required: Confirm booking, send payment link, and follow up within 2 hours.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    logger.info("BOOKING TEAM NOTIFICATION:\n%s", message)

    # Send to webhook if configured (Make.com receives and forwards to WhatsApp)
    if NOTIFICATION_WEBHOOK_URL:
        try:
            requests.post(
                NOTIFICATION_WEBHOOK_URL,
                json={
                    # Human-readable message for Slack / email fallback
                    "text": message,
                    # Structured fields for Make.com WhatsApp module
                    "customer_name": customer_name,
                    "customer_email": customer_email,
                    "customer_phone": customer_phone or "",
                    "package": f"{pkg_name} ({package_id})",
                    "travel_date": travel_date,
                    "passengers": pax_details,
                    "accommodation": f"{accommodation_id or 'TBC'} / {room_type or 'TBC'}",
                    "price_quoted_usd": str(total_quoted_usd or "TBC"),
                    "priority": priority,
                    "summary": conversation_summary,
                    # Auth token for Make.com's WhatsApp module
                    "whatsapp_token": WHATSAPP_API_TOKEN,
                },
                timeout=5,
            )
        except Exception as e:
            logger.warning("Webhook notification failed: %s", e)

    return {
        "success": True,
        "message": (
            f"Booking team notified. They will contact {customer_email} "
            f"within 2 hours with confirmation and payment details."
        ),
        "contact_details": {
            "whatsapp": COMPANY_WHATSAPP,
            "email": COMPANY_EMAIL_BOOKINGS,
        },
    }


# ─────────────────────────────────────────────────────────────
# Tool: escalate_to_human
# ─────────────────────────────────────────────────────────────

def escalate_to_human(
    reason: str,
    priority: str = "normal",
    customer_name: str | None = None,
    customer_contact: str | None = None,
    conversation_summary: str = "",
    booking_reference: str | None = None,
) -> dict:
    """
    Escalate conversation to a human agent.
    Priority: low | normal | high | urgent
    """
    alert = f"""
🚨 ESCALATION REQUIRED — {priority.upper()}
━━━━━━━━━━━━━━━━━━━
Reason: {reason}
Customer: {customer_name or 'Unknown'} | Contact: {customer_contact or 'Not provided'}
Booking Ref: {booking_reference or 'N/A'}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

Summary:
{conversation_summary}
━━━━━━━━━━━━━━━━━━━
"""
    logger.warning("ESCALATION:\n%s", alert)

    if NOTIFICATION_WEBHOOK_URL:
        try:
            requests.post(
                NOTIFICATION_WEBHOOK_URL,
                json={"text": f"@here {alert}" if priority == "urgent" else alert},
                timeout=5,
            )
        except Exception as e:
            logger.warning("Escalation webhook failed: %s", e)

    response_time = {
        "urgent": "within 10 minutes",
        "high": "within 1 hour",
        "normal": "within 2-4 hours",
        "low": "next business day",
    }.get(priority, "within 2-4 hours")

    return {
        "escalated": True,
        "priority": priority,
        "response_time": response_time,
        "human_contact": {
            "whatsapp": COMPANY_WHATSAPP,
            "email": COMPANY_EMAIL_BOOKINGS,
            "phone": COMPANY_PHONE,
        },
        "message_to_customer": (
            f"I've alerted our team and they will be in touch {response_time}. "
            f"You can also reach them directly on WhatsApp: {COMPANY_WHATSAPP}"
        ),
    }


# ─────────────────────────────────────────────────────────────
# Tool registry (maps tool names to functions for agent dispatch)
# ─────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, Any] = {
    "search_packages": search_packages,
    "get_package_details": get_package_details,
    "calculate_pricing": calculate_pricing,
    "get_accommodation_options": get_accommodation_options,
    "get_seasonal_context": get_seasonal_context,
    "create_lead": create_lead,
    "notify_booking_team": notify_booking_team,
    "escalate_to_human": escalate_to_human,
}


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Dispatch a tool call by name and return the result."""
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return {"error": f"Tool '{tool_name}' is not available."}
    try:
        return fn(**tool_input)
    except ToolError as e:
        return {"error": str(e)}
    except TypeError as e:
        logger.exception("Tool call parameter error for '%s': %s", tool_name, e)
        return {"error": f"Parameter error calling {tool_name}: {e}"}
    except Exception as e:
        logger.exception("Unexpected error in tool '%s'", tool_name)
        return {"error": f"An unexpected error occurred: {e}"}
