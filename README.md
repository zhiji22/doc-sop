# Doc SOP AI

AI tool that converts documents into SOP, checklist and structured knowledge.

## Stack

Frontend
- Next.js
- Clerk Auth
- Tailwind

Backend
- FastAPI
- PostgreSQL (Supabase)
- MinIO (S3 compatible storage)

AI
- LLM API (OpenAI / Dashscope / etc.)

## Features

- Document upload
- SOP generation
- Checklist extraction
- Structured JSON output
- History runs
- Authentication

## Development

### Start storage

```bash
docker compose up -d


##  Supabase
https://supabase.com/dashboard/project/ifwydlcuhfgaushkxihy/database/settings
## MinlO Console
http://localhost:9001/browser/doc-sop
## Clerk
https://dashboard.clerk.com/apps/app_3AOHsnGJ0zau75BC2RSiPzTJmuO/instances/ins_3AOHsnrVEd903pUvyF0IOaU1RDP/api-keys