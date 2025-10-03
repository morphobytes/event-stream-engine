# Event Stream Engine

A Python project for event stream processing.

## Setup

### Virtual Environment

This project uses a Python virtual environment located in `.venv/` (hidden directory).

To activate the virtual environment:

```bash
# On Linux/macOS
source .venv/bin/activate

# On Windows
.venv\Scripts\activate
```

To deactivate:
```bash
deactivate
```

### Installing Dependencies

After activating the virtual environment:

```bash
pip install --upgrade pip
# Install your project dependencies here
# pip install -r requirements.txt
```

## Project Structure

**Finalized Repository Structure** - Use this as a blueprint for maintaining the project repository:

```
`/event-stream-engine` ⬅️ (Project Root)
├── `.github/`                  # CI/CD and Version Control
├── `.venv/`                    # Virtual environment (ignored by Git)
├── `app/`                      # The Core Application Source Code
│   ├── `api/`                  # Flask Routes (Webhooks & Public API)
│   ├── `core/`                 # Business Logic, Data Contracts (SQLAlchemy models)
│   ├── `runner/`               # Asynchronous Campaign Runner (Celery/Tasking logic)
│   ├── `ingestion/`            # File Processing Logic (CSV/JSON upload)
│   └── `main.py`               # Application entry point (Initializes Flask, Celery, DB)
├── `client/`                   # Minimal Front End (UI)
├── `tests/`                    # Testing Suite (Unit, E2E)
├── **`Dockerfile`**            # Multi-stage container definition
├── **`docker-compose.yml`**   # Local orchestration (Web, DB, Redis, Worker)
├── `requirements.txt`          # Python dependencies
├── `README.md`                 # Project documentation (REQUIRED)
└── `documentation.md`          # Architectural decisions & DDL (REQUIRED)
```