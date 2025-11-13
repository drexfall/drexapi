# drexapi

A small modular FastAPI project structured for easy development and Docker deployment.

MongoDB connection is centralized and reusable across the app.

What’s wired now
- app/db/session.py creates a global MongoClient with ServerApi('1') using MONGODB_URI.
- App startup pings MongoDB and creates a unique index on users.email.
- FastAPI endpoints get a db via Depends(get_db).

Configure
- Copy .env.example to .env and set MONGODB_URI and MONGO_DB.
- For MongoDB Atlas, use your srv URI and password.

Run locally
```bash
# install
pip install -r requirements.txt

# run API
uvicorn app.main:app --reload
```

Docker
```bash
docker compose up --build
```

Env vars
- MONGODB_URI: e.g. mongodb://mongo:27017/drex (local) or mongodb+srv://user:password@host/?appName=core (Atlas)
- MONGO_DB: database name

Notes
- Requires dnspython for mongodb+srv (already in requirements).
- On startup, a ping is executed; failures are logged to stdout.

Project layout (important files):

- app/main.py — FastAPI application factory and startup actions
- app/api/v1 — API package with versioned endpoints and Pydantic schemas
- app/db — MongoDB helpers and session (pymongo)
- app/core/config.py — configuration via pydantic BaseSettings
- requirements.txt — Python dependencies
- Dockerfile — container image build
- docker-compose.yml — compose file for local deployment (includes MongoDB)

Quick start (local):

1. Create a virtual environment and install dependencies:

   python -m venv .venv
   .venv\Scripts\activate (Windows) or source .venv/bin/activate (Unix)
   pip install -r requirements.txt

2. Run the app with uvicorn:

   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

3. Open docs at: http://127.0.0.1:8000/docs

Run with Docker (recommended):

1. Start services using docker compose (this will run a local MongoDB):

   docker compose up --build

2. The web app will be available at http://127.0.0.1:8000

Notes:
- This example uses MongoDB (pymongo). For production, secure your Mongo instance and consider managed services.
- Passwords are hashed with passlib (bcrypt). No authentication/authorization is included.

API Endpoints (v1):
- POST /api/v1/users — create user (body: email, password)
- GET /api/v1/users — list users
- GET /api/v1/users/{id} — retrieve user by id
