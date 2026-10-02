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

### Changed

- Python 3.11 is the oldest version the server runs on. It already was in practice: the
  speech model runtime it depends on publishes nothing for 3.10, so an install there
  failed before starting.
