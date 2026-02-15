
# NextBus

**Never miss your bus again.**

NextBus tells you exactly when to leave your house to catch the next bus—accounting for your walk time to the stop.

---

## Why NextBus?

Ever found yourself:
- 🏃 Running to catch a bus you thought you had time for?
- ❄️ Standing at a cold bus stop, wondering when the next bus will actually arrive?
- 📱 Checking multiple apps to figure out if you should leave right now?

**NextBus solves this.** It wraps the MBTA real-time API and gives you one number: **minutes until you need to leave**.

---

## What Is It?

NextBus is a **self-hosted API** that:

1. **Tracks your configured bus routes** (Route 77 to Harvard, Route 350 to Burlington, etc.)
2. **Gets real-time predictions** from MBTA (~12 second updates)
3. **Accounts for your walk time** (4 minutes to the stop? It factors that in)
4. **Tells you when to leave** with a simple `leave_in_minutes` field

**For example:**
- Bus arrives in 8 minutes
- Your walk is 4 minutes
- **NextBus says: "Leave in 4 minutes"** ✅

---

## Who Is It For?

### If You're Building a Consumer App

NextBus is designed to be consumed by **your own apps**:
- 🖥️ **ESP32 e-ink displays** - Dedicated mini screen by your door
- 🏠 **Home Assistant** - Sensors and automations
- 📱 **Mobile apps** - iOS/Android with real-time updates
- 🌐 **Web dashboards** - Family calendar with bus times

**Start here:** Copy the **[consumer-kit/](consumer-kit/)** folder to your project. It contains:
- Full API documentation
- Example responses for offline testing
- Cursor rules template for rapid development

### If You're a Developer Exploring This Repo

You're looking at a **production-ready API service** with:
- ✅ **API v1 stable** - Strong versioning guarantees, won't break your clients
- ✅ **Real-time first** - Live predictions with static schedule fallback
- ✅ **Resilient** - Serves stale cache when MBTA is unreachable (up to 5 min)
- ✅ **Well-documented** - Specs, ADRs, and comprehensive examples
- ✅ **Docker-ready** - Runs anywhere (Raspberry Pi, NAS, cloud)

---

## Quick Start

### Get It Running (5 minutes)

```bash
# 1. Clone and enter the repo
git clone https://github.com/emsimadr/nextbus-core.git
cd nextbus-core

# 2. Configure your bus stops
cp config.example.yaml config.yaml
# Edit config.yaml with your routes, stops, and walk times

# 3. Add your MBTA API key (get one free at api-v3.mbta.com)
cp .env.example .env
# Edit .env with your MBTA_API_KEY

# 4. Run with Docker
docker compose up -d

# 5. Test it
curl http://localhost:8080/v1/board
```

**You should see JSON with your bus arrivals!** 🎉

---

## API at a Glance

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/board` | All configured stops |
| `GET /v1/board/{key}` | Single stop by config key |
| `GET /health` | Health check (no auth) |

### Example Response

```json
{
  "key": "77_harvard",
  "label": "77 - Harvard",
  "status": "ok",
  "arrival": {
    "time": "2026-02-15T14:12:00-05:00",
    "minutes": 8,
    "leave_in_minutes": 4,  ← This is what you care about!
    "source": "realtime"
  },
  "alternatives": [ ... ]
}
```

**Interactive docs:** http://localhost:8080/docs (when running)

---

## How It Works (High Level)

```
You → NextBus API → MBTA Real-Time API
                  ↓
         ┌─────────────────┐
         │ 1. Get predictions │
         │ 2. Fall back to schedule if empty │
         │ 3. Compute when you need to leave │
         │ 4. Cache for 20s │
         │ 5. Serve stale if MBTA is down │
         └─────────────────┘
                  ↓
         JSON Response with
         leave_in_minutes
```

**Key Design Decisions:**
- Uses **arrival time** (when doors open) not departure time → gives you 30-60s buffer to board
- **Conservative by design** → better to arrive early than miss the bus
- **Caches for 20 seconds** → avoids hitting MBTA rate limits
- **Serves stale data** → if MBTA is unreachable, uses cache up to 5 minutes old

*Why these choices matter:* See [spec/FunctionalSpec.md](spec/FunctionalSpec.md) for detailed rationale

---

## Project Structure (For Developers)

```
nextbus-core/
├── api/                 API contract artifacts (OpenAPI, schemas, examples)
│   └── CONTRACT.md         Versioning policy - read this if building a client
│
├── consumer-kit/        Everything client developers need
│   ├── README.md           API documentation for consumers
│   ├── sample.cursorrules  Copy to your project
│   └── examples/           Response examples for offline testing
│
├── spec/                Product & functional specs (source of truth)
│   ├── PRD.md              What we're building and why
│   ├── FunctionalSpec.md   How endpoints behave
│   ├── MBTA-API.md         MBTA integration details
│   └── ...
│
├── adr/                 Architecture Decision Records
│   └── 0001-*.md           Why we made key technical choices
│
├── src/                 Application code (Python/FastAPI)
│   ├── app.py              FastAPI application
│   ├── board.py            Board service (orchestration)
│   ├── mbta_client.py      MBTA API wrapper
│   ├── cache.py            TTL cache with stale mode
│   ├── selection.py        Arrival filtering & sorting
│   └── models.py           Pydantic response models
│
├── test/                Tests (unit, integration, e2e)
├── config.yaml          Your bus stops (create from config.example.yaml)
├── .env                 Your secrets (create from .env.example)
└── docker-compose.yml   One-command deployment
```

---

## Why These Docs Exist

This project separates **what** from **how**:

- **README.md (you are here)** → The "why" and "what" at a glance
- **[consumer-kit/README.md](consumer-kit/README.md)** → For app developers consuming the API
- **[spec/](spec/)** → Detailed functional specs, the "how" and source of truth
- **[adr/](adr/)** → Why we made specific architectural decisions

If you're exploring the codebase, start here. If you're building a client app, start with `consumer-kit/`. If you're contributing or understanding behavior, dive into `spec/`.

---

## API Stability Guarantee

**This is API version 1. It's stable.**

Within v1, these will **never break**:
- ✅ Endpoint paths (`/v1/board`, `/v1/board/{key}`)
- ✅ Field names and types
- ✅ Enum values (`ok`, `stale`, `realtime`, `schedule`, etc.)
- ✅ HTTP status codes

You can hard-code field names. They won't change.

**If we ever need breaking changes:** We'll create `/v2/` and maintain `/v1/` for at least 6 months.

See [api/CONTRACT.md](api/CONTRACT.md) for full versioning policy.

---

## Real-World Use Cases

### ESP32 E-Ink Display by Your Door
```
┌─────────────────────┐
│  Route 77           │
│  Leave in 4 min     │  ← Updates every 20s
│  Bus arrives 8 min  │
│                     │
│  Next: 23 min       │
└─────────────────────┘
```

### Home Assistant Automation
```yaml
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.route_77_leave_in_minutes
        below: 5
    action:
      - service: notify.mobile_app
        data:
          message: "Leave now! Bus in 9 minutes"
```

### Family Dashboard
Show all family members which buses are coming and when each person needs to leave based on their configured walk times.

---

## Development

### Run Tests
```bash
pip install -r requirements-dev.txt
pytest                    # All tests
pytest --cov=src          # With coverage
pytest -m smoke           # Smoke tests (requires MBTA API key)
```

### Contributing

1. Read [spec/FunctionalSpec.md](spec/FunctionalSpec.md) - Understand the behavior
2. Check [plan/](plan/) - See what's in scope
3. Write an ADR for architectural changes - See [adr/0000-template.md](adr/0000-template.md)
4. Follow [.cursorrules](.cursorrules) - Coding standards and API stability rules

**Important:** This is an API with external consumers. Breaking changes are expensive. Read [api/CONTRACT.md](api/CONTRACT.md) before changing responses.

---

## Technology

- **Python 3.12** with type hints
- **FastAPI** for the API (with auto-generated OpenAPI docs)
- **Pydantic** for data validation and response models
- **httpx** for async MBTA API calls
- **Docker** for deployment (runs anywhere)

---

## License & Credits

**License:** MIT (see LICENSE file)

**MBTA Data:** Powered by the MBTA v3 API. Use of MBTA data is governed by the [MassDOT Developers License Agreement](https://www.mbta.com/developers/v3-api/best-practices).

Built for people who just want to know when to leave the house to catch their bus. 🚌

---

## Questions?

- **For API consumers:** See [consumer-kit/README.md](consumer-kit/README.md)
- **For behavior details:** See [spec/FunctionalSpec.md](spec/FunctionalSpec.md)
- **For architecture decisions:** See [adr/](adr/)
- **For issues:** Open a GitHub issue
