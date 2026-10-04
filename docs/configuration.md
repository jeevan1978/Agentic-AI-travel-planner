# Configuration and troubleshooting

Run commands from the project root. Create `.env` from `.env.example` only if it does not exist. The backend loads it with python-dotenv. React must never receive provider secrets.

## Keys

| Variable | Use |
| --- | --- |
| `GROQ_API_KEY` | Live blueprint/day planning |
| `GROQ_MODEL` | Optional; default `openai/gpt-oss-120b` |
| `IGNAV_API_KEY` | Live Flight quotes |
| `IGNAV_MARKET` | Optional; default IN |
| `OPENWEATHER_API_KEY` | Weather forecasts |
| `STAYING_API_KEY` | Live accommodation; sandbox keys/fixtures rejected |
| `STAY_SEARCH_URL` | Optional; default `https://api.stayingapi.com/v1/search` |
| `WIKIPEDIA_USER_AGENT` | Application identity and real contact; no API key needed |

Train requires positive user-entered one-way railway distance, not an API key. Tested low-level railway search/service utilities remain available, but normal validated requests always supply distance. `RAIL_DISTANCE_URL` and `RAIL_DISTANCE_API_KEY` apply only to direct utility use, not the UI workflow.

## Train estimates

Edit `config/transport_rates.json` for rates and taxes:

| Class | INR per km | Configured tax |
| --- | ---: | ---: |
| SL — Sleeper | 0.60 | 0% |
| 3A — AC 3-Tier | 1.20 | 5% |
| 2A — AC 2-Tier | 1.80 | 5% |
| 1A — AC First Class | 2.40 | 5% |

These are estimates, not official ticket tariffs. Tax reference is recorded in the configuration. Reservation, superfast, catering and other charges are excluded.

```text
base per person = round(distance × configured rate, 2)
tax per person  = round(base × configured tax rate, 2)
party per leg   = (base + tax) × travelers
```

Decimal uses ROUND_HALF_UP. Both legs use the entered one-way distance. Do not enter a round-trip distance.

## Troubleshooting

| Symptom | Explanation/action |
| --- | --- |
| Train button disabled | Enter finite railway distance greater than zero |
| Weather unavailable | Five-day forecast cannot cover dates outside provider results; check closer to travel |
| Groq daily quota warning | Wait for quota or configure an account/model with remaining capacity |
| No schedule | Check Groq key, model access, quota and backend logs |
| Stay unavailable | Replace sandbox key with live credentials; provider must return real inventory |
| Partial budget | Missing costs are excluded; subtotal cannot confirm affordability |
| Flight unavailable | Check key/date/airport resolution; uppercase IATA codes avoid ambiguous city search |
| Connection error | Start backend at port 8080; check `/docs` |
| Changes not visible | Restart backend after Python edits and refresh the UI |

## Verification

```powershell
python -m pytest -q
```

From `frontend/`:

```powershell
npm ci
npm run build
npm run lint
```

Default tests use doubles rather than live provider/model calls. Enable `RUN_LIVE_TESTS=1` and `pytest -m integration` for live verification. These calls consume quota and depend on credentials, inventory and network. Diagnostic `output/` snapshots are never loaded as fallback facts.
