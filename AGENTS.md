# AI Agent Context & Guidelines (AGENTS.md)

Welcome. If you are an AI agent assisting with this codebase, you must adhere to the context and architectural rules outlined in this document. 

## 1. Project Identity: The "Monolithic Sandbox"
This is **not** a traditional single-purpose application. This project is a unified, multi-purpose workspace where the developer will combine various unrelated utilities and applications into a single backend. 
- **Examples of features:** Bookmark management, Todo tracking, Telegram archiving, etc.
- **CRITICAL RULE:** Do **NOT** create separate subprojects, independent microservices, or complex nested "apps" for new features. All features must live together within the root-level layer directories.

## 2. Directory Structure & Architecture
The project follows a flat, layered architecture at the root level. When adding new features (like a Todo app or a Telegram archiver), integrate them into the existing directories:

- `routers/`: All FastAPI HTTP endpoints. Add new features as new router files (e.g., `routers/todo_router.py`, `routers/bookmark_router.py`) and include them in `main.py`.
- `services/`: Core business logic and database interactions. Keep routers thin by moving logic here.
- `schemas/`: Pydantic models for request validation and response serialization.
- `db/models.py`: **ALL** SQLAlchemy ORM models go here. We use strictly declarative style mapping inheriting from `db.models.Base`. Do not create multiple `models.py` files.
- `db/config.py`: Contains the async engine and `get_db` dependency.
- `core/settings.py`: Multi-environment Pydantic settings.

## 3. Technology Stack & Best Practices
- **Package Manager**: Use `uv` (e.g., `uv add <package>`, `uv run <command>`).
- **Framework**: Asynchronous FastAPI.
- **Database ORM**: SQLAlchemy 2.0 (Strictly Asynchronous).
  - Use `AsyncSession` for all database operations.
  - Use the `get_db` dependency from `db.config` to inject database sessions into FastAPI routers.
- **Migrations**: Alembic (`uv run alembic revision --autogenerate -m "..."`).

## 4. Environment Profiles
The application context switches based on the `APP_ENV` environment variable (`dev`, `prod`, `testing`):
- **Development/Production**: Uses PostgreSQL via `asyncpg`.
- **Testing**: Forces `APP_ENV=testing` via `tests/conftest.py` and uses an isolated SQLite database via `aiosqlite`. 

## 5. Future Expansions
When asked to implement new interfaces, adhere to these guidelines:
- **CLI Tools**: If a CLI is requested, add it to this repository rather than creating a new project. You can use standard Python CLI libraries (like `click`, `argparse`, or `typer`) and place scripts at the root or within a `cli/` folder, utilizing the existing `services` and `db` functions.
- **Server-Rendered Pages**: If templating is requested (e.g., Jinja2), add a `templates/` folder at the root and serve HTML directly from the FastAPI routers using `fastapi.templating.Jinja2Templates`.

## 6. Living Document (Updating AGENTS.md)
This file is a living document. If you, as an AI agent, and the user make a significant architectural decision, introduce a new core pattern, or add a major top-level directory (e.g., setting up a `cli/` directory or a new core dependency like Redis), you **MUST** update this `AGENTS.md` file to reflect those new patterns. Always ensure the context here stays up-to-date for future agent sessions.

## Summary
Keep it simple, flat, and asynchronous. Every new capability is just another router, another service, another schema, and another model in the existing files/folders.
