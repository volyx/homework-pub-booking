"""Ex5 — reference solution for tools.py.

This is the educator's reference. Copy ONLY INTO starter/ via
`make educator-apply-solution`. Never commit. The .gitignore at the
repo root excludes this whole solution/ directory.

Pedagogical notes (why each tool is implemented this way):

- venue_search, get_weather, calculate_cost are marked parallel_safe.
  They read fixtures, don't mutate anything. The executor can batch them
  in one turn — important for Decision 5 (parallelism) from the course.

- generate_flyer writes a file, so parallel_safe=False. If you miss
  this, the grader deducts points and the student gets interleaved
  writes in race scenarios.

- Every tool calls record_tool_call() before returning. The integrity
  check compares later outputs (the flyer) against this log to detect
  fabrication.

- Tools return ToolResult, not raw dicts. ToolResult lets the executor
  see success/failure distinctly and surface the summary to the LLM.

- Bad inputs raise ToolError with SA_TOOL_* error_code. Never RuntimeError.
  The executor catches ToolError and feeds it to the LLM as a tool call
  result; RuntimeError would crash the whole session.
"""

from __future__ import annotations

import json
from pathlib import Path

from sovereign_agent.errors import ToolError
from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

from starter.edinburgh_research.integrity import record_tool_call

_SAMPLE_DATA = (
    Path(__file__).parent.parent.parent / "starter" / "edinburgh_research" / "sample_data"
)


# ---------------------------------------------------------------------------
# 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    venues_path = _SAMPLE_DATA / "venues.json"
    if not venues_path.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", f"venues.json not found at {venues_path}")

    try:
        venues = json.loads(venues_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", f"venues.json malformed: {e}") from e

    near_l = near.lower().strip()
    results = [
        v
        for v in venues
        if v.get("open_now")
        and near_l in v.get("area", "").lower()
        and v.get("seats_available_evening", 0) >= party_size
        and (v.get("hire_fee_gbp", 0) + v.get("min_spend_gbp", 0)) <= budget_max_gbp
    ]

    output = {
        "near": near,
        "party_size": party_size,
        "budget_max_gbp": budget_max_gbp,
        "results": results,
        "count": len(results),
    }
    record_tool_call(
        "venue_search",
        {"near": near, "party_size": party_size, "budget_max_gbp": budget_max_gbp},
        output,
    )

    return ToolResult(
        success=True,
        output=output,
        summary=f"venue_search({near!r}, party={party_size}): {len(results)} result(s)",
    )


# ---------------------------------------------------------------------------
# 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    weather_path = _SAMPLE_DATA / "weather.json"
    if not weather_path.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", f"weather.json not found at {weather_path}")

    data = json.loads(weather_path.read_text(encoding="utf-8"))
    city_key = city.lower().strip()

    if city_key not in data:
        return ToolResult(
            success=False,
            output={"error": f"no weather data for city {city!r}"},
            summary=f"get_weather({city!r}, {date}): city not found",
            error_code="SA_TOOL_INVALID_INPUT",
        )

    # Fixture shape: {"edinburgh": {"2026-04-25": {...}, ...}}
    city_forecasts = data[city_key]
    match = city_forecasts.get(date) if isinstance(city_forecasts, dict) else None
    if match is None:
        return ToolResult(
            success=False,
            output={
                "error": f"no forecast for {city} on {date}",
                "available_dates": sorted(city_forecasts.keys())
                if isinstance(city_forecasts, dict)
                else [],
            },
            summary=f"get_weather({city!r}, {date}): date not in fixture",
            error_code="SA_TOOL_INVALID_INPUT",
        )

    output = {"city": city, "date": date, **match}
    record_tool_call("get_weather", {"city": city, "date": date}, output)
    return ToolResult(
        success=True,
        output=output,
        summary=f"get_weather({city!r}, {date}): {match['condition']}, {match['temperature_c']}C",
    )


# ---------------------------------------------------------------------------
# 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    catering_path = _SAMPLE_DATA / "catering.json"
    venues_path = _SAMPLE_DATA / "venues.json"

    catering = json.loads(catering_path.read_text(encoding="utf-8"))
    venues = json.loads(venues_path.read_text(encoding="utf-8"))

    if catering_tier not in catering["base_rates_gbp_per_head"]:
        return ToolResult(
            success=False,
            output={"error": f"unknown catering_tier: {catering_tier}"},
            summary=f"calculate_cost: bad tier {catering_tier!r}",
            error_code="SA_TOOL_INVALID_INPUT",
        )

    venue = next((v for v in venues if v.get("id") == venue_id), None)
    if venue is None:
        return ToolResult(
            success=False,
            output={"error": f"unknown venue_id: {venue_id}"},
            summary=f"calculate_cost: venue {venue_id!r} not found",
            error_code="SA_TOOL_INVALID_INPUT",
        )

    base_per_head = catering["base_rates_gbp_per_head"][catering_tier]
    modifier = catering["venue_modifiers"].get(venue_id, 1.0)
    hours = max(1, duration_hours)
    subtotal = int(base_per_head * modifier * party_size * hours)
    service = int(subtotal * catering["service_charge_percent"] / 100)
    venue_floor = venue.get("hire_fee_gbp", 0) + venue.get("min_spend_gbp", 0)
    total = subtotal + service + venue_floor

    # Deposit rules
    if total < 300:
        deposit = 0
    elif total < 1000:
        deposit = int(total * 0.2)
    else:
        deposit = int(total * 0.3)

    output = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": subtotal,
        "service_gbp": service,
        "venue_floor_gbp": venue_floor,
        "total_gbp": total,
        "deposit_required_gbp": deposit,
    }
    record_tool_call(
        "calculate_cost",
        {
            "venue_id": venue_id,
            "party_size": party_size,
            "duration_hours": duration_hours,
            "catering_tier": catering_tier,
        },
        output,
    )
    return ToolResult(
        success=True,
        output=output,
        summary=f"calculate_cost({venue_id}, party={party_size}): total £{total}, deposit £{deposit}",
    )


# ---------------------------------------------------------------------------
# 4 — generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    required = (
        "venue_name",
        "date",
        "time",
        "party_size",
        "condition",
        "temperature_c",
        "total_gbp",
    )
    missing = [k for k in required if k not in event_details]
    if missing:
        return ToolResult(
            success=False,
            output={"error": f"missing event_details keys: {missing}"},
            summary=f"generate_flyer: missing {missing}",
            error_code="SA_TOOL_INVALID_INPUT",
        )

    lines = [
        f"# {event_details['venue_name']} — Private Event",
        "",
        f"**Date:** {event_details['date']}  ",
        f"**Time:** {event_details['time']}  ",
        f"**Party size:** {event_details['party_size']}  ",
    ]
    if event_details.get("venue_address"):
        lines.append(f"**Address:** {event_details['venue_address']}  ")

    lines.extend(
        [
            "",
            "## Weather forecast",
            f"{event_details['condition'].capitalize()}, {event_details['temperature_c']}°C",
            "",
            "## Cost",
            f"Total: £{event_details['total_gbp']}",
        ]
    )
    deposit = event_details.get("deposit_required_gbp", 0)
    if deposit:
        lines.append(f"Deposit required: £{deposit}")
    else:
        lines.append("No deposit required for this booking.")

    flyer_md = "\n".join(lines) + "\n"

    flyer_path = session.workspace_dir / "flyer.md"
    flyer_path.parent.mkdir(parents=True, exist_ok=True)
    flyer_path.write_text(flyer_md, encoding="utf-8")

    output = {
        "path": "workspace/flyer.md",
        "bytes_written": flyer_path.stat().st_size,
        # Record the facts we wrote into the flyer — integrity check reads this.
        "venue_name": event_details["venue_name"],
        "total_gbp": event_details["total_gbp"],
        "deposit_required_gbp": deposit,
    }
    record_tool_call("generate_flyer", {"event_details": event_details}, output)
    return ToolResult(
        success=True,
        output=output,
        summary=f"generate_flyer: wrote workspace/flyer.md ({flyer_path.stat().st_size} bytes)",
    )


# ---------------------------------------------------------------------------
# Registry — same signature as starter scaffold
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {"city": {"type": "string"}, "date": {"type": "string"}},
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,
            examples=[{"input": {"city": "Edinburgh", "date": "2026-04-25"}, "output": {}}],
        )
    )

    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,
            examples=[
                {
                    "input": {"venue_id": "haymarket_tap", "party_size": 6, "duration_hours": 3},
                    "output": {},
                }
            ],
        )
    )

    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write a markdown flyer for the event to workspace/flyer.md.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file
            examples=[{"input": {"event_details": {"venue_name": "Haymarket Tap"}}, "output": {}}],
        )
    )

    return reg


__all__ = ["build_tool_registry", "venue_search", "get_weather", "calculate_cost", "generate_flyer"]
