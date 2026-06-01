# Jobscape Backend

A full-featured job portal REST API built with FastAPI. Jobscape connects job seekers with employers, offering resume parsing, AI-powered ATS scoring, NLP-based skill extraction, Cloudinary media handling, Google OAuth, and transactional email via SMTP and Resend.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [Seeding the Database](#seeding-the-database)
- [Running the Server](#running-the-server)
- [API Overview](#api-overview)
- [Authentication](#authentication)

---

## Overview

Jobscape is a two-sided job platform. Employers can post jobs with defined skill requirements, ATS thresholds, and selection processes. Job seekers can upload resumes, apply to listings, and receive automatic match scores based on parsed resume data. An admin layer handles platform-level moderation and verification.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Database | PostgreSQL (via psycopg / psycopg2) |
| Migrations | Alembic |
| Auth | JWT (PyJWT, python-jose), Google OAuth |
| NLP | spaCy (en_core_web_sm) |
| File Storage | Cloudinary |
| PDF Parsing | pdfplumber, PyMuPDF, pdfminer.six |
| Email | SMTP (Gmail) |
| Rate Limiting | SlowAPI |
| Background Tasks | APScheduler |
| Server | Uvicorn |

---

## Features

**Job Seekers**
- Register, verify email, and manage profile
- Upload and parse resumes (PDF, DOCX)
- Automatic skill extraction via spaCy NLP
- Apply to jobs with cover letters
- Receive ATS match scores against job requirements

**Employers**
- Register with tiered verification (email-verified, fully-verified)
- Post jobs with required and preferred skills, experience level, work mode, salary, and ATS threshold
- Review ranked applicant pools with ATS reports
- Manage selection rounds and application statuses
- Upload company assets via Cloudinary

**Admin**
- Full platform oversight
- Employer verification management
- User and job moderation

**Platform**
- Google OAuth login
- JWT-based authentication with refresh token support
- Rate limiting on sensitive endpoints
- Sentry error tracking
- Scheduled background jobs via APScheduler

---

## Project Structure

```
Jobscape_Backend/
├── app/
│   ├── main.py               # FastAPI app entry point
│   ├── database.py           # SQLAlchemy engine and session
│   ├── models/               # ORM models (User, Job, Employer, JobSeeker, etc.)
│   ├── routers/              # Route handlers grouped by domain
│   ├── schemas/              # Pydantic request and response schemas
│   ├── services/             # Business logic layer
│   └── utils/                # Security, NLP, PDF parsing helpers
├── alembic/                  # Database migration scripts
├── seed_data.py              # Database seeder for development and testing
├── email_ver.py              # Email verification utility
├── test_login.py             # Login test script
├── .env.example              # Environment variable template
└── requirements.txt
```

---

## Getting Started

**Prerequisites**

- Python 3.11+
- PostgreSQL 14+
- A Cloudinary account
- An SMTP-enabled email account (Gmail recommended)

**Installation**

```bash
git clone https://github.com/ayeshamashiat/Jobscape_Backend.git
cd Jobscape_Backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Install the spaCy language model
python -m spacy download en_core_web_sm
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_USER` | Database username |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_DB` | Database name |
| `POSTGRES_HOST` | Database host |
| `POSTGRES_PORT` | Database port |
| `JWT_SECRET_KEY` | Secret key for signing JWTs |
| `ALGORITHM` | JWT algorithm (e.g. `HS256`) |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |
| `FRONTEND_URL` | Frontend origin URL (used for CORS and email links) |
| `EMAIL_HOST` | SMTP host (e.g. `smtp.gmail.com`) |
| `EMAIL_PORT` | SMTP port (e.g. `587`) |
| `SMTP_EMAIL` | Sender email address |
| `SMTP_PASSWORD` | Sender email password or app password |

---

## Database Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after changing models
alembic revision --autogenerate -m "describe your change"
```

---

## Seeding the Database

The seeder creates an admin account, two test employers, several job listings, and 25 candidate profiles with varied skill sets to test ATS scoring.

```bash
python -m app.seed_data
```

---

## Running the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

---

## API Overview

| Domain | Base Path |
|---|---|
| Authentication | `/auth` |
| Job Seekers | `/job-seekers` |
| Employers | `/employers` |
| Jobs | `/jobs` |
| Applications | `/applications` |
| Admin | `/admin` |

Full schema documentation is available via the auto-generated Swagger UI at `/docs` or ReDoc at `/redoc`.

---

## Authentication

All protected endpoints require a Bearer token in the Authorization header.

```
Authorization: Bearer <your_access_token>
```

Tokens are obtained via the login endpoint. Google OAuth is also supported for social login. Email verification is required before a newly registered account can access protected routes.
