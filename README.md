
# Bus Tracker API

A realtime bus arrival tracking API that tells you when to leave your house to catch the next bus.

Designed for **separate consumer applications** in their own repos (ESP32, Home Assistant, mobile apps, etc.) with strong API stability guarantees.

## For Client Developers

Building an app that consumes this API? Copy the **[consumer-kit/](consumer-kit/)** folder to your project. It contains everything you need:

- **`README.md`** - Full API documentation
- **`sample.cursorrules`** - Copy to your project as `.cursorrules`
- **`examples/`** - Response examples for offline testing

## Consumer Applications

These apps live in **separate repositories**:

- **ESP32 e-ink display** - Dedicated mini screen
- **Home Assistant** - REST sensor (see spec/HomeAssistant.md)
- **TRMNL plugin** - Future e-ink dashboard tile
- **Community clients** - Your app here!

## Quick start

```bash
# 1. Copy and edit the config (stops, labels, walk times)
cp config.example.yaml config.yaml

# 2. Copy and edit secrets (API keys)
cp .env.example .env
# Edit .env with your MBTA API key

# 3. Run
docker compose up -d

# 4. Check
curl http://localhost:8080/v1/board
```

## API

| Endpoint              | Purpose                          |
| --------------------- | -------------------------------- |
| `GET /v1/board`       | All configured stops             |
| `GET /v1/board/{key}` | Single stop by config key        |
| `GET /health`         | Health check                     |

See **[api/CONTRACT.md](api/CONTRACT.md)** for versioning policy and stability guarantees.

Interactive API docs (when running): [http://localhost:8080/docs](http://localhost:8080/docs)

## Configuration

- **`config.yaml`** -- your bus stops, labels, walk times, cache settings (safe to share)
- **`.env`** -- your API keys and secrets (never share or commit)

See `config.example.yaml` and `.env.example` for templates with comments.

## Development

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests (unit + integration + e2e)
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run smoke tests (requires real MBTA API key)
pytest -m smoke
```

## Project structure

```
api/                API contract artifacts
├── CONTRACT.md        Versioning policy and stability guarantees
├── openapi.json       OpenAPI 3.0 specification (auto-generated)
├── schemas/           JSON schemas for validation (auto-generated)
└── examples/          Example responses

consumer-kit/       Self-contained package for consumer app developers
├── README.md          Full API documentation
├── sample.cursorrules Cursor rules template for consumer projects
└── examples/          Response examples for offline testing

spec/               Product and functional specs (source of truth)
adr/                Architecture decision records
plan/               Iteration plans and backlog
src/                Application source code
test/               Tests and fixtures
scripts/            Utility scripts (API spec export, etc.)
```

## Specs

Agents must treat `spec/` as the source of truth. Work in slices defined in `plan/Iteration-01.md`.
Any architecture changes require an ADR in `adr/`.
