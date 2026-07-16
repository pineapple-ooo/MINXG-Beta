# Changelog

All notable changes to this project will be documented in this file.

---

## [0.18.3] - 2026-07-16 (shitshow cleanup)

### Added — Because Apparently We Didn't Have Enough Shit Already

#### Agent Framework (4 new tools)
- `react_agent` — ReAct agent with reasoning traces, because single-step thinking is for amateurs
- `planning_agent` — Task decomposition and planning, for when you need to think before you act
- `multi_agent_system` — Multi-agent orchestration, because one agent wasn't enough chaos
- `self_reflective_agent` — Self-reflective agent that learns from its own damn mistakes

#### RAG System (3 new tools)
- `vector_store` — In-memory vector store with cosine similarity search
- `text_splitter` — Text chunking for embedding, because context windows aren't infinite
- `rag_pipeline` — Complete RAG pipeline with hybrid search (keyword + semantic)

#### Workflow Engine (2 new tools)
- `workflow_engine` — DAG-based workflow execution with conditional branching, loops, retries
- `workflow_builder` — Fluent API for building workflows without losing your mind

#### Function Calling (3 new tools)
- `function_registry` — Function registry with OpenAI-compatible format
- `structured_output` — Pydantic-based structured output generation
- `tool_calling_agent` — Agent that automatically calls tools based on LLM responses

#### Streaming (4 new tools)
- `streaming_response` — Server-Sent Events (SSE) streaming
- `token_stream` — Token-by-token streaming with callbacks
- `chunk_aggregator` — Aggregate streaming chunks into structured output
- `stream_parser` — Parse and process streaming responses

#### Guardrails (3 new tools)
- `input_guardrail` — Input validation with injection detection, PII redaction, toxicity filtering
- `output_guardrail` — Output validation with hallucination detection, repetition checks
- `guardrails` — Combined input/output guardrail system

#### Caching (3 new tools)
- `semantic_cache` — Semantic cache using embedding similarity
- `tiered_cache` — Multi-level caching (L1 memory, L2 disk, L3 semantic)
- `cache_middleware` — Automatic caching middleware for API calls

#### Monitoring (4 new tools)
- `metrics_collector` — Real-time metrics collection (counters, gauges, histograms)
- `request_tracker` — Request latency tracking and token usage monitoring
- `alert_manager` — Alert rules with webhook notifications
- `health_checker` — System health monitoring and checks

#### CLI Commands (15 new commands)
- `minxg memory` — Memory system dashboard
- `minxg cost` — Cost tracking panel
- `minxg compare` — Multi-model comparison
- `minxg web` — Launch web UI
- `minxg features` — Feature showcase
- `minxg themes` — Theme management
- `minxg export` — Export memories
- `minxg import` — Import memories
- `minxg ext` — Extension management
- `minxg screen` — Screen operations
- `minxg update` — Update check
- `minxg skill` — Skill management
- `minxg bench` — Performance benchmark
- `minxg replay` — Session replay
- `minxg doctor` — System diagnosis

#### Worker Tools (69 new tools)
- **File workers (9):** file_read, file_write, file_copy, file_move, file_delete, file_search, file_diff, file_hash, file_stat
- **Network workers (9):** http_get, http_post, dns_lookup, ping, port_scan, whois, url_parse, ssl_lookup, tcp_socket
- **Crypto workers (9):** aes_encrypt, aes_decrypt, hash, hmac, pbkdf2, sign, verify, keygen, random_bytes
- **Math workers (7):** calculator, statistics, linear_algebra, calculus, fft, primes, geometry
- **Text workers (9):** text_process, summarize, translate, sentiment, keywords, entities, regex, diff, plagiarism
- **System workers (9):** system_info, process, disk, memory, cpu, network_interfaces, environment, uptime, file_descriptors
- **AI workers (10):** ai_chat, embeddings, classify, extract, ocr, speech_to_text, text_to_speech, summarize_long, question_answer, image_tools
- **Image tools (17):** format_convert, resize, thumbnail, metadata, compress, crop, rotate, filters, grayscale, histogram, batch_convert, watermark, collage, gif_create, exif_extract, color_analysis, image_compare
- **Audio tools (10):** format_convert, metadata, trim, merge, volume, silence_removal, speed_change, audio_extract, normalize, fade
- **Video tools (14):** format_convert, metadata, trim, merge, resize, frame_extract, video_from_frames, audio_extract, add_audio, compress, speed_change, thumbnail, video_to_gif, subtitles
- **PDF tools (11):** merge, split, extract_pages, extract_text, extract_images, add_watermark, rotate, compress, pdf_to_images, get_info
- **Data tools (17):** csv_read, csv_write, csv_to_json, csv_stats, json_read, json_write, json_query, json_merge, yaml_read, yaml_write, yaml_to_json, xml_read, xml_to_json, validate_json, validate_yaml, filter_rows, sort_data

#### Other Additions
- `SELLING_POINTS.md` — Complete list of 190+ selling points with competitor comparison
- `docs/README.md` — Comprehensive documentation
- `examples/README.md` — Example code directory
- `.github/workflows/ci.yml` — GitHub Actions CI/CD
- `scripts/benchmark.py` — Performance benchmark script
- `scripts/setup.sh` — Setup script
- `CHANGELOG.md` — This changelog
- `CONTRIBUTING.md` — Contributing guide

### Changed
- README completely rewritten with aggressive English slang tone
- All documentation updated to match the new attitude

### Fixed
- Everything that was broken (we think)
- Probably introduced new bugs (that's how it works, right?)

### Removed
- Our sanity
- Any hope of sleeping tonight
- The illusion that this project would ever be "done"

---

## [0.18.2] - 2026-07-15

### Added
- Memory system with multi-tier storage
- Cost tracking functionality
- Theme system with 8 themes
- Model comparison feature
- Web UI
- Export/import functionality

### Changed
- MCP server implementation
- README rewritten (again)

### Fixed
- Various bugs that we're not going to talk about

---

## [0.18.1] - 2026-07-14

### Added
- Initial MCP server support
- 70+ worker tools
- Basic CLI commands

### Changed
- Project structure reorganization

### Fixed
- Critical bugs that prevented the thing from running

---

## [0.18.0] - 2026-07-13

### Added
- Initial release
- 8 pillars of MINXG
- Basic worker framework
- CLI interface

### Notes
- This was the beginning of our collective breakdown
- We thought 50 tools was enough. We were wrong.

---

*Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).*
*This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html), mostly.*
