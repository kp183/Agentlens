# Changelog

All notable changes to the `agentlens-py` package are documented in this file.

## [0.2.1] - 2026-10-28

### Added
- **Configurable Prompt & Completion Capture**: Added `capture_prompts` and `capture_completions` options to `al.init(...)` and `AgentLensClient`, supporting programmatic configuration and environment variable overrides (`AGENTLENS_CAPTURE_PROMPTS`, `AGENTLENS_CAPTURE_COMPLETIONS`).
- **Field-Level Data Redaction**: Added `redact_fields` and `redact_fn` to sanitize sensitive key-value pairs in inputs/outputs recursively with default `"[REDACTED]"` masking or custom transform functions (`AGENTLENS_REDACT_FIELDS`).
- **Silent Tracing Diagnostic Warning**: Emits a single one-time warning when a root function decorated with `@al.trace` finishes with zero recorded LLM spans across its subtree, alerting developers to missing instrumentation calls (`al.instrument_openai()` / `al.instrument_anthropic()`). Supports both sync and async coroutine functions.

### Fixed
- **Quick Start & README Documentation**: Standardized installation instructions across all documentation and snippets to `pip install agentlens-py`, added prerequisites note for local port availability, and clarified live API key requirements vs. offline demo.

### Changed
- **Metadata & Python Support**: Updated Python version requirement to `>=3.11` to match tested environments, and added project repository and documentation URLs.

> [!NOTE]
> Micro-cent cost formatting precision updates (`<$0.0001`) are dashboard-only (frontend UI) and do not affect SDK numeric cost calculations.

## [0.2.0] - 2026-06-15
- Initial public release of `agentlens-py` SDK.
