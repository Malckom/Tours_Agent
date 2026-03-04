"""
Tool schemas for the Kenya Group Joining Safaris AI Agent (Safi).
Uses OpenAI-compatible format (Groq / OpenAI API).
"""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_packages",
            "description": (
                "Search available safari packages. Call this when a customer asks what "
                "packages are available, especially if they mention destinations, duration, "
                "or budget. Returns a summary list of matching packages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destinations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of desired destinations, e.g. ['Nairobi', 'Masai Mara']",
                    },
                    "budget_per_person_usd": {
                        "type": "number",
                        "description": "Maximum budget per person in USD",
                    },
                    "accommodation_level": {
                        "type": "string",
                        "enum": ["budget", "mid_range", "upmarket", "luxury", "any"],
                        "description": "Preferred accommodation tier. Use 'any' if not specified.",
                    },
                    "duration_days": {
                        "type": "number",
                        "description": "Desired safari duration in days. Use 0.5 for half-day, 3 for 3-day etc.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_package_details",
            "description": (
                "Get the full details for a specific package by its ID. Use this when a "
                "customer wants to know more about a specific safari — itinerary, inclusions, "
                "exclusions, wildlife, packing list, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "package_id": {
                        "type": "string",
                        "description": "Package ID. Known IDs: 'NNP-HALF-DAY' (Nairobi NP), 'MARA-3DAY-2N' (Masai Mara 3-day)",
                    },
                },
                "required": ["package_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_pricing",
            "description": (
                "Calculate the total price for a safari booking including transport, park fees, "
                "and accommodation. ALWAYS use this tool before quoting any price to a customer. "
                "Never estimate prices from training knowledge."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "package_id": {
                        "type": "string",
                        "description": "Package ID: 'NNP-HALF-DAY' or 'MARA-3DAY-2N'",
                    },
                    "travel_date_str": {
                        "type": "string",
                        "description": "Travel/departure date in YYYY-MM-DD format",
                    },
                    "pax": {
                        "type": "array",
                        "description": "List of passenger groups by type",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["adult", "child"]},
                                "count": {"type": "integer"},
                            },
                            "required": ["type", "count"],
                        },
                    },
                    "accommodation_id": {
                        "type": "string",
                        "description": (
                            "Accommodation ID for Masai Mara packages. Options: "
                            "'MARA-CHUI', 'EMAIYAN', 'OLMORAN', 'ENKOROK', "
                            "'JAMBO-MARA', 'SOPA', 'MITI-MINGI', 'RHINO', 'FLAIR'"
                        ),
                    },
                    "room_type": {
                        "type": "string",
                        "enum": ["single", "double", "triple"],
                        "description": "Room type: single (own room), double (2 sharing), triple (3 sharing)",
                    },
                    "nights": {
                        "type": "integer",
                        "description": "Number of accommodation nights (default 2 for Mara 3-day package)",
                    },
                    "group_size_in_vehicle": {
                        "type": "integer",
                        "description": "Total passengers in shared vehicle (affects per-person transport rate for NNP)",
                    },
                    "include_park_fees": {
                        "type": "boolean",
                        "description": "Whether to include park fees in the quote (default: true)",
                    },
                    "addons": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional add-ons: 'giraffe_centre', 'david_sheldrick_elephant_orphanage'",
                    },
                },
                "required": ["package_id", "travel_date_str", "pax"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_accommodation_options",
            "description": (
                "Get the list of accommodation options for the Masai Mara package, "
                "optionally filtered by category. Use this when a customer asks about "
                "camp/lodge options or wants to compare accommodation choices."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "package_id": {
                        "type": "string",
                        "description": "Package ID (default: 'MARA-3DAY-2N')",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Budget", "Mid-range", "Upmarket", "Luxury"],
                        "description": "Filter by accommodation category",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_seasonal_context",
            "description": (
                "Get season information, migration status, and current park fees for a "
                "specific travel date. Use this to answer questions about the best time "
                "to visit, migration timing, or to understand what season a date falls in."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "travel_date_str": {
                        "type": "string",
                        "description": "Date to check in YYYY-MM-DD format. Omit for today.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": (
                "Log a customer's booking intent as a lead. Call this once a customer has "
                "provided their name, email, and chosen package/date. This records the "
                "inquiry for follow-up by the booking team."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "nationality": {"type": "string"},
                    "package_id": {"type": "string"},
                    "travel_date": {"type": "string"},
                    "pax_count": {
                        "type": "number",
                        "description": "Total number of passengers (integer)",
                    },                    "accommodation_id": {"type": "string"},
                    "room_type": {"type": "string"},
                    "notes": {"type": "string", "description": "Any special requests or notes from the conversation"},
                },
                "required": ["first_name", "last_name", "email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_booking_team",
            "description": (
                "Send a booking handoff notification to the booking team when a customer "
                "is ready to book. Include the full booking summary so the team can follow "
                "up promptly. Call this AFTER create_lead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "customer_email": {"type": "string"},
                    "customer_phone": {"type": "string"},
                    "package_id": {"type": "string"},
                    "travel_date": {"type": "string"},
                    "pax_details": {"type": "string", "description": "e.g. '2 adults, 1 child'"},
                    "accommodation_id": {"type": "string"},
                    "room_type": {"type": "string"},
                    "total_quoted_usd": {"type": "number"},
                    "conversation_summary": {
                        "type": "string",
                        "description": "2-3 sentence summary of what the customer wants and any special notes",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                    },
                },
                "required": [
                    "customer_name",
                    "customer_email",
                    "package_id",
                    "travel_date",
                    "pax_details",
                    "conversation_summary",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Escalate the conversation to a human agent. Use for: emergencies on safari, "
                "payment issues, complaints, complex modifications, and any situation where "
                "the customer explicitly asks to speak to a person."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Clear reason for escalation"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                        "description": "urgent = safety/emergency; high = payment/imminent departure; normal = general",
                    },
                    "customer_name": {"type": "string"},
                    "customer_contact": {"type": "string"},
                    "conversation_summary": {"type": "string"},
                    "booking_reference": {"type": "string"},
                },
                "required": ["reason", "priority", "conversation_summary"],
            },
        },
    },
]
