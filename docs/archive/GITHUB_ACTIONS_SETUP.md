# GitHub Actions Setup

Automated daily briefing runs Monday-Friday at 9:30 AM ET via GitHub Actions.

---

## Prerequisites

- GitHub repository with code pushed
- API keys for OpenAI, Exa, AssemblyAI
- Gmail credentials for email delivery
- Supabase database configured

---

## Add Secrets

Go to repository Settings → Secrets and variables → Actions

Add the following repository secrets:

**Required:**
- `DATABASE_URL` - Postgres connection string from Supabase
- `SUPABASE_URL` - Project URL (https://PROJECT_ID.supabase.co)
- `SUPABASE_API_KEY` - Anon/public key from Supabase
- `OPENAI_API_KEY` - OpenAI API key
- `EXA_API_KEY` - Exa search API key
- `ASSEMBLYAI_API_KEY` - AssemblyAI transcription key
- `SMTP_EMAIL` - Gmail address for sending emails
- `SMTP_PASSWORD` - Gmail app password (16 characters from myaccount.google.com/apppasswords)
- `EMAIL_RECIPIENT` - Email address to receive briefings

**Optional (for newsletters):**
- `GMAIL_CREDENTIALS_BASE64` - Base64-encoded gmail_credentials.json
- `GMAIL_TOKEN_BASE64` - Base64-encoded gmail_token.pickle
- `LANGSMITH_API_KEY` - LangSmith observability (optional)

### Encoding Gmail files for GitHub

```bash
base64 -i gmail_credentials.json | pbcopy
base64 -i gmail_token.pickle | pbcopy
```

Paste the output as the secret value.

---

## Workflow Schedule

Default: Monday-Friday at 9:30 AM ET (14:30 UTC)

To change schedule, edit `.github/workflows/morning-briefing.yml`:

```yaml
schedule:
  - cron: '30 14 * * 1-5'  # 9:30 AM EST = 14:30 UTC, Mon-Fri
```

Common times (EST → UTC):
- 6:00 AM EST = `0 11 * * 1-5`
- 7:00 AM EST = `0 12 * * 1-5`
- 8:00 AM EST = `0 13 * * 1-5`
- 9:30 AM EST = `30 14 * * 1-5`

---

## Manual Trigger

Go to Actions tab → Morning Briefing → Run workflow

Workflow inputs allow selective execution:
- `run_agent_search` - Enable/disable AI agent search
- `run_newsletters` - Enable/disable newsletter processing
- `run_podcasts` - Enable/disable podcast processing
- `test_mode` - Use TEST_MODE for reduced API costs

---

## Troubleshooting

### Secrets not found
Verify secret names match exactly (case-sensitive). Re-add secret if unsure.

### Gmail app password not working
- Use 16-character app password from myaccount.google.com/apppasswords
- NOT your regular Gmail password
- Remove any spaces from the password

### Workflow not running automatically
- GitHub Actions can be delayed up to 15 minutes
- Repos inactive >60 days have workflows automatically disabled
- Check Actions tab is enabled in repository settings

### Email not received
- Check GitHub Actions logs for errors
- Verify SMTP credentials are correct
- Check spam folder
- Confirm EMAIL_RECIPIENT is set

### Newsletter OAuth failed
- Must generate gmail_token.pickle locally first (run `python tests/test_newsletter.py`)
- Encode both gmail_credentials.json and gmail_token.pickle to base64
- Add as GMAIL_CREDENTIALS_BASE64 and GMAIL_TOKEN_BASE64 secrets

### Database connection errors
- Verify DATABASE_URL format: `postgresql://postgres:PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres`
- Check password has no special URL characters that need encoding
- Confirm database tables exist (run supabase_schema.sql)

---

## Monitoring

View logs: Actions tab → Click workflow run → Click job → Expand steps

Expected execution time: 2-3 minutes

Cost: $0 (2,000 free minutes/month, uses ~150 minutes/month)

---

## Cost Estimates

**GitHub Actions:** Free (150 min/month used of 2,000 free)

**API costs per run:**
- Agent search: $0.03
- Newsletter enrichment: $0.02
- Podcasts (cached): $0.01
- **Total:** ~$0.06/day = ~$1.80/month (Mon-Fri only)


