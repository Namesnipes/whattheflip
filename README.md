# WhatTheFlip

This project helps you find the best deals on groceries.

## Getting Started

### Prerequisites

*   Docker and Docker Compose
*   A `.env` file in the `backend` directory (see below).

### Environment Variables

Before starting, you need to set up environment variables for the backend:

1.  Create a `.env` file in the `backend` directory (i.e., `backend/.env`).
2.  Add the following environment variables to it, replacing placeholders with your actual values:
    ```env
    DATABASE_URL=postgresql://user:password@db:5432/whattheflipdb
    GOOGLE_API_KEY=your_google_api_key_here
    ```
    *   `DATABASE_URL`: The connection string for the PostgreSQL database. The default values match the `docker-compose.yml`.
    *   `GOOGLE_API_KEY`: Your API key for Google Gemini.

### Running the Application

With Docker and Docker Compose installed, and the `backend/.env` file configured, you can start the entire application (database, backend, and frontend) with a single command from the root directory of the project:

```bash
docker-compose up --build
```

*   The `--build` flag is recommended for the first time or when Dockerfiles or application dependencies change. For subsequent starts, `docker-compose up` is usually sufficient.
*   This command will build the necessary Docker images and start all the services defined in `docker-compose.yml`.

Once started:
*   The **backend API** will be accessible at `http://localhost:8001`.
*   The **frontend application** will be accessible at `http://localhost:5173`.

### Database Migrations

If you make changes to the database models (in `backend/app/db/models.py`), you'll need to generate and apply database migrations.

1.  **Generate a new migration script (after model changes):**
    Open a terminal and ensure your Docker containers are running (`docker-compose up`). Then execute:
    ```bash
    docker-compose exec backend alembic revision -m "your_migration_message_here"
    ```
    Replace `"your_migration_message_here"` with a short description of the changes (e.g., "add_user_email_field"). This will create a new migration file in `backend/alembic/versions/`.

2.  **Edit the new migration script:**
    Open the newly generated migration file and fill in the `upgrade()` and `downgrade()` functions with the necessary schema changes using Alembic's operations.

3.  **Apply the migrations:**
    After editing the migration script, apply it to the database:
    ```bash
    docker-compose exec backend alembic upgrade head
    ```
    This command applies all pending migrations to the database.

## Project Structure
