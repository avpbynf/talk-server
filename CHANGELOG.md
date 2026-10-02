# Changelog

All notable changes to this project are documented in this file.

Based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

### Changed

- Python 3.11 is the oldest version the server runs on. It already was in practice: the
  speech model runtime it depends on publishes nothing for 3.10, so an install there
  failed before starting.
