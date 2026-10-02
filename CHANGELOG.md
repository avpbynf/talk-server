# Changelog

All notable changes to this project are documented in this file.

Based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- `GET /v1/models` lists the loaded model. It needs a valid token, so a client can
  tell a refused token (401) from a good one without sending audio. Asking it is not
  counted as usage, so a client checking its token every few seconds leaves the token
  statistics alone.
- The server announces itself on the local network over mDNS (`_talk._tcp.local.`)
  once the model is loaded, so Talk clients can find it. Set `MDNS_ENABLED=false` to
  turn it off. Under Docker the announcement only leaves the container with
  `network_mode: host`. A failed announcement logs a warning and never stops the
  server.
- A Talk client can now get a token by pairing: it asks for a request, and you read
  it a 6-digit code that shows in the server log (WARNING) and under "Pairing
  Requests" in the `/admin/` dashboard. Typing the code on the client mints a token
  named `<client name> (paired)`. Codes last two minutes, five wrong tries cancel the
  request, and five requests can wait at once, one per machine. Ten wrong codes in
  total turn pairing off until the server restarts. Pairing is off while `ADMIN_TOKEN` is
  empty (the startup warning says so), and `PAIRING_ENABLED=false` turns it off. The
  mDNS record carries `pairing=1` or `pairing=0` accordingly.

### Changed

- Python 3.11 is the oldest version the server runs on. It already was in practice: the
  speech model runtime it depends on publishes nothing for 3.10, so an install there
  failed before starting.

### Fixed

- `PORT` now sets the port in the container and under `make dev`. Both used to listen
  on 8000 whatever it said.
