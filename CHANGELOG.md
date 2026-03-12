# Changelog

Tüm önemli değişiklikler bu dosyada belgelenir.
Format: [Conventional Commits](https://www.conventionalcommits.org/)

## [1.0.1] - 2025-07-16

### Fixed

- fix: add `load_dotenv()` call in `main()` so `.env` file is loaded for local runs (python-dotenv was in requirements.txt but never called)

## [1.0.0] - 2025-07-15

### Added

- feat: Full Python rewrite of PHP UAVT crawler
- feat: OOP architecture with Clean Architecture patterns (client/models/repository/services)
- feat: DaskClient with automatic token management, retry logic, and rate limiting
- feat: HtmlParser for street, building, and section HTML table parsing
- feat: PostgreSQL repository with bulk upsert (ON CONFLICT) for all hierarchy levels
- feat: Database migrations (auto table creation with proper FK constraints and indexes)
- feat: Checkpoint-based progress tracking (JSON file, resume after crash)
- feat: Configurable crawl scope (START_CITY_CODE / END_CITY_CODE filters)
- feat: CLI with --migrate, --status, --reset flags
- feat: Docker Compose for PostgreSQL 16
- docs: Comprehensive README with setup, usage, and architecture docs
- docs: OpenAPI/Swagger specification for DASK API
- test: Unit tests for DaskClient (token, retry, rate limiting)
- test: Unit tests for HtmlParser (streets, buildings, sections, onclick extraction)
- test: Unit tests for Crawler (hierarchy traversal, checkpoint resume, JSON parsing)
