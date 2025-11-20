# Supabase Setup

PostgreSQL database for caching transcripts, insights, and deduplication.

---

## Create Project

1. Go to https://supabase.com
2. Create new project
3. Choose region (closest to you)
4. Set database password (save this)
5. Wait for project initialization (~2 minutes)

---

## Get Credentials

### Project URL and API Key

Go to Project Settings → API

Copy:
- Project URL: `https://PROJECT_ID.supabase.co`
- Anon/public key: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

### Database Password

Go to Project Settings → Database

Find connection string under "Connection parameters" → URI tab

Format: `postgresql://postgres:PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres`

If you forgot password, reset it in Database settings.

---

## Configure Environment

Add to `.env`:

```bash
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres
SUPABASE_URL=https://PROJECT_ID.supabase.co
SUPABASE_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Replace:
- `YOUR_PASSWORD` - Your database password
- `PROJECT_ID` - Your project ID from URL

---

## Run Database Schema

1. Go to Supabase dashboard → SQL Editor
2. Click "New query"
3. Copy contents of `supabase_schema.sql` from project root
4. Paste and run (Ctrl/Cmd + Enter)
5. Verify success: Check Tables section shows:
   - `content_items`
   - `insights`
   - `briefings`

---

## Test Connection

```bash
python tests/test_supabase_connection.py
```

Expected output:
```
Database connection successful
Tables exist: content_items, insights, briefings
```

---

## Connection Pooler

For GitHub Actions, use connection pooler (port 6543):

```bash
DATABASE_URL=postgresql://postgres:PASSWORD@aws-1-us-east-1.pooler.supabase.com:6543/postgres
```

Advantages:
- Better for serverless/short-lived connections
- Handles connection pooling automatically
- Prevents "too many connections" errors

For local development, either format works.

---

## Troubleshooting

### Connection refused
- Check DATABASE_URL format is correct
- Verify password has no special characters needing URL encoding
- Confirm project is not paused (free tier pauses after inactivity)

### Password authentication failed
- Reset password in Project Settings → Database
- Update DATABASE_URL with new password
- Check for extra spaces in password

### SSL connection error
Add `?sslmode=require` to DATABASE_URL:
```bash
DATABASE_URL=postgresql://postgres:PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres?sslmode=require
```

### Tables don't exist
- Run supabase_schema.sql in SQL Editor
- Check for errors in execution
- Verify you're connected to correct project

### Too many connections
- Use connection pooler (port 6543)
- Or increase connection limit in Database settings (paid plans)

### IPv4 vs IPv6 issues
Use direct database URL (db.PROJECT_ID) not pooler if IPv6 causes issues.


