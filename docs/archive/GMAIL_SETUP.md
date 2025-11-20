# Gmail Setup

OAuth setup for newsletter fetching and email delivery.

---

## Gmail OAuth for Newsletters

### Enable Gmail API

1. Go to https://console.cloud.google.com
2. Create project (or select existing)
3. Enable Gmail API: APIs & Services → Library → Search "Gmail API" → Enable
4. Create OAuth credentials:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Download JSON file

### Configure OAuth Credentials

1. Rename downloaded file to `gmail_credentials.json`
2. Place in `podcast-summarizer/` directory (not backend/)
3. Run first authentication:

```bash
python tests/test_newsletter.py
```

4. Browser opens → Sign in → Grant Gmail read-only access
5. Token saved to `gmail_token.pickle` (auto-generated)

### OAuth Consent Screen

If you see "This app isn't verified":

1. Go to APIs & Services → OAuth consent screen
2. Add your email to "Test users"
3. Save changes
4. Re-run authentication

### For GitHub Actions

Encode both files to base64:

```bash
base64 -i podcast-summarizer/gmail_credentials.json | pbcopy
base64 -i podcast-summarizer/gmail_token.pickle | pbcopy
```

Add as GitHub secrets:
- `GMAIL_CREDENTIALS_BASE64`
- `GMAIL_TOKEN_BASE64`

Workflow automatically decodes them to correct locations.

---

## Gmail App Password for Email Delivery

Used by SMTP to send briefing emails.

### Generate App Password

1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and device
3. Copy 16-character password
4. Add to `.env`:

```bash
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
EMAIL_RECIPIENT=recipient@email.com
```

Do NOT use your regular Gmail password.

---

## Supported Newsletters

### TLDR AI
- From: `dan@tldrnewsletter.com`
- Parser: `parse_tldr_ai`

### Morning Brew
- From: `crew@morningbrew.com`
- Subject contains: "Morning Brew"
- Parser: `parse_morning_brew`

### Add New Newsletter

Edit `backend/ingestion/gmail_newsletters.py`:

```python
NEWSLETTER_CONFIGS = {
    "your_newsletter": {
        "name": "Newsletter Name",
        "from_email": "sender@newsletter.com",
        "subject_contains": "Optional subject filter",
        "priority": 3,
        "parser": "parse_your_newsletter"  # Implement this function
    }
}
```

Implement parser function to extract article links from HTML.

---

## Troubleshooting

### gmail_credentials.json not found
- Check file is in `podcast-summarizer/` directory (NOT backend/)
- File name must be exactly `gmail_credentials.json`

### OAuth consent screen not configured
- Add your email to test users in Google Cloud Console
- OAuth consent screen → Test users → Add email

### Access blocked: This app's request is invalid
- Verify OAuth credentials are for "Desktop app" type
- Check redirect URIs include `http://localhost`

### Gmail authentication failed in GitHub Actions
- Verify GMAIL_CREDENTIALS_BASE64 and GMAIL_TOKEN_BASE64 secrets are set
- Re-encode files if changed
- Check workflow decodes to correct directory (podcast-summarizer/)

### OAuth token expired
```bash
rm podcast-summarizer/gmail_token.pickle
python tests/test_newsletter.py
```

### SMTP authentication failed
- Verify using app password (16 characters), not regular password
- Check SMTP_EMAIL and SMTP_PASSWORD in .env
- Test with: `python tests/test_newsletter.py`

### Rate limiting
Gmail API quota: 1 billion quota units/day (default)
Newsletter fetching uses ~5 units per email
Unlikely to hit limit with daily fetching


