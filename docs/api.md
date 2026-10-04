# API contract

Base URL: http://localhost:8080. Schema: `/docs`. `POST /api/plan` and `POST /plan-trip` execute the same graph.

## Request

| Field | Requirement/default |
| --- | --- |
| `source_city`, `destination` | Required nonempty strings; Flight also accepts uppercase IATA codes |
| `start_date`, `end_date` | ISO dates; 1–30 inclusive days |
| `budget` | Nonnegative INR number or text such as `30000 INR`; default 0 |
| `passengers` | Integer 1–100; default 1 |
| `transport_mode` | Flight or Train; default Flight; Bus rejected |
| `train_class` | SL, 3A, 2A or 1A; default 3A |
| `rail_distance_km` | Finite positive one-way distance; required for Train |
| `hotel_type` | Preference string; default Budget; star filter currently not enforced |
| `interests` | List of strings; default empty |
| `random_seed` | Integer; default 0; candidate sampling only |
| `day_locations` | Optional one nonempty location per day; changes bases/stays, not transport legs |

## Train example

600 km below is hypothetical test input. Replace it with the railway distance for your route.

```json
{
  "source_city": "Bangalore",
  "destination": "Goa",
  "start_date": "2026-10-10",
  "end_date": "2026-10-13",
  "passengers": 2,
  "budget": "30000 INR",
  "transport_mode": "Train",
  "train_class": "3A",
  "rail_distance_km": 600,
  "hotel_type": "3-star",
  "interests": ["Beaches", "Culture", "Food"],
  "random_seed": 17
}
```

This gives four days, three nights and two transport legs. At the configured rates, hypothetical 600 km in 3A is INR 720 base + 36 tax per person, 1512 for two travelers per leg, 3024 for both. A leg's estimate is recorded when the model requests its tool.

For Flight, set mode to Flight and omit distance or send null. No train rate or fake airfare fallback is used.

## Response fields

| Field | Contents |
| --- | --- |
| `status` | success means workflow completion, not all-provider success |
| `data.metadata` | Request context, total_days, planning_status |
| `data.transport` | Leg records with optional quote/estimate result |
| `data.accommodation` | Stay-period records with optional result |
| `data.days` | DayPlan list with weather, hotel, sourced schedules and warnings |
| `data.budget` | known_subtotal, complete, status, entries and missing_costs |
| `data.randomization` | seed and candidate-selection decisions |
| `data.warnings` | Missing information and failure explanations |
| `data.tool_trace` | day/date/location, tool, args, result and cached flag |

Planning status COMPLETE requires scheduled days without warnings. PARTIAL means some schedule exists but information/days are missing or warnings exist. FAILED means no morning/afternoon/evening schedule exists.

Budget OVER_BUDGET means known costs already exceed a positive budget. PARTIAL means costs are missing; remaining budget cannot confirm compliance. WITHIN_BUDGET requires all tracked costs known. Food/activity costs are currently unavailable, so normal budgets remain incomplete.

HTTP 422 indicates invalid input, including Train without distance. HTTP 500 indicates unexpected graph failure. Individual provider failures normally become unavailable results and warnings inside a completed response.

## Native tools

| Tool | Boundary |
| --- | --- |
| `get_weather` | Exact current location/date |
| `search_transport` | Only leg_id; executor supplies route/date/passengers |
| `search_stay` | Only stay_id; executor supplies period/location/guests |
| `search_wikipedia` | query/category (places or food); executor supplies current location |
| `random_choice` | Existing unique candidate_ids and valid count |

Each executed call produces a matching ToolMessage. Trace observations show what was actually retrieved.
