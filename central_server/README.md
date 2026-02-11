# LTS Central Signal Relay

This service receives Telegram signals once and relays them to many running LTS clients.

## Run locally

```bash
cd central_server
python -m pip install -r requirements.txt
LTS_TELEGRAM_BOT_TOKEN=... python server.py
```

## Required environment variables

- `LTS_TELEGRAM_BOT_TOKEN`: Telegram bot token used by relay server.

## Optional environment variables

- `LTS_ENTRY_SIGNAL_CHANNEL_ID` (default: `-1002171239233`)
- `LTS_RISK_SIGNAL_CHANNEL_ID` (default: `-1003096527269`)
- `LTS_SIGNAL_RELAY_HOST` (default: `0.0.0.0`)
- `LTS_SIGNAL_RELAY_PORT` (default: `8080`)
- `LTS_SIGNAL_RELAY_TELEGRAM_POLL_TIMEOUT` (default: `2`)
- `LTS_SIGNAL_RELAY_TELEGRAM_REQUEST_TIMEOUT` (default: `10`)
- `LTS_SIGNAL_RELAY_TELEGRAM_POLL_LIMIT` (default: `100`)
- `LTS_SIGNAL_RELAY_MAX_EVENTS` (default: `5000`)
- `LTS_SIGNAL_RELAY_MAX_RESPONSE_LIMIT` (default: `100`)
- `LTS_SIGNAL_RELAY_SYNC_MAX_BATCHES` (default: `300`)
- `LTS_SIGNAL_RELAY_OFFSET_PATH` (default: `/tmp/lts-signal-relay-offset.json`)
- `LTS_SIGNAL_RELAY_TOKEN` (optional shared token for client auth)

## API

- `GET /health`
- `GET /api/v1/offset/latest`
- `GET /api/v1/signals?after_id=0&limit=100&client_id=...`

If `LTS_SIGNAL_RELAY_TOKEN` is configured, send header:

- `X-LTS-Relay-Token: <token>`

## LTS client configuration (user EXE)

Run each LTS client in relay mode so users do not need their own Telegram bot token:

- `LTS_SIGNAL_SOURCE_MODE=relay`
- `LTS_SIGNAL_RELAY_BASE_URL=https://<your-relay-domain>`
- `LTS_SIGNAL_RELAY_CLIENT_ID=<optional-client-id>` (optional, defaults from API key hash)
- `LTS_SIGNAL_RELAY_TOKEN=<same token as server>` (only when relay token auth is enabled)

In relay mode, `LTS_TELEGRAM_BOT_TOKEN` is not required on user PCs.

## Cloudtype deployment tip

Use this same repository and set the service root directory to `central_server`.
