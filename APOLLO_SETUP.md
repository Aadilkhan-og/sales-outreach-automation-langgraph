# Apollo.io Integration Setup Guide

This guide explains how to use Apollo.io for lead extraction in your sales outreach automation application.

## 📋 Overview

The application now supports **three methods** for managing leads:

1. **Apollo CSV Export** (Easiest - No API key needed)
2. **Apollo API** (Requires API key)
3. **Supabase** (Optional - For persistent storage)

---

## 🚀 Method 1: Apollo CSV Export (Recommended)

### Step 1: Export Leads from Apollo.io

1. Log in to your Apollo.io account
2. Go to your saved searches or create a new search
3. Select the leads you want to export
4. Click **"Export"** and download as CSV
5. Save the CSV file to your project directory

### Step 2: Update .env File

```env
APOLLO_CSV_PATH="./leads.csv"
```

Replace `./leads.csv` with the path to your exported CSV file.

### Step 3: Run the Application

The application is already configured to use CSV by default in `main.py`:

```python
lead_loader = ApolloLeadLoader(
    csv_file_path=os.getenv("APOLLO_CSV_PATH")
)
```

### CSV Format

Your Apollo CSV should have these columns (Apollo exports include these by default):

- `# Id` or `Id`
- `Name` or `First Name` + `Last Name`
- `Email`
- `Title`
- `Company` or `Organization`
- `LinkedIn` or `Person Linkedin Url`
- `Company LinkedIn Url`
- `Website`
- `Industry`
- `Phone`
- `City`, `State`, `Location`
- `Status` (optional - defaults to "NEW")

See `leads_sample.csv` for an example format.

---

## 🔑 Method 2: Apollo API

### Step 1: Get Your Apollo API Key

1. Log in to Apollo.io
2. Go to Settings → Integrations → API
3. Copy your API key

### Step 2: Update .env File

```env
APOLLO_API_KEY="your-actual-apollo-api-key"
```

### Step 3: Update main.py

Uncomment the Apollo API loader in `main.py`:

```python
# Option 2: Use Apollo.io API (requires API key)
lead_loader = ApolloLeadLoader(
    api_key=os.getenv("APOLLO_API_KEY")
)
```

### API Features

- Real-time lead fetching
- Direct integration with Apollo database
- No CSV export needed
- Supports people and company searches

### API Limitations

- Free tier has rate limits
- Updating lead status requires paid plan or external tracking
- API responses may differ from CSV exports

---

## 💾 Method 3: Supabase (Optional)

Use Supabase when you need:

- Persistent lead storage
- Real-time status updates
- Multi-user access
- Custom lead tracking fields

### Step 1: Create Supabase Project

1. Go to https://supabase.com
2. Create a new project
3. Copy your Project URL and API Key

### Step 2: Create Leads Table

Run this SQL in Supabase SQL Editor:

```sql
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "Name" TEXT,
    "Email" TEXT UNIQUE,
    "Title" TEXT,
    "Company" TEXT,
    "LinkedIn" TEXT,
    "Company LinkedIn" TEXT,
    "Website" TEXT,
    "Industry" TEXT,
    "Phone" TEXT,
    "Location" TEXT,
    "Status" TEXT DEFAULT 'NEW',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add index for faster queries
CREATE INDEX idx_leads_email ON leads("Email");
CREATE INDEX idx_leads_status ON leads("Status");
```

### Step 3: Update .env File

```env
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-supabase-anon-key"
SUPABASE_TABLE_NAME="leads"
```

### Step 4: Update main.py

```python
# Option 3: Use Supabase for persistent storage
lead_loader = SupabaseLeadLoader(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY"),
    table_name=os.getenv("SUPABASE_TABLE_NAME", "leads")
)
```

### Sync Apollo to Supabase

You can sync Apollo leads to Supabase for persistence:

```python
# Load from Apollo CSV
apollo_loader = ApolloLeadLoader(csv_file_path="./leads.csv")

# Sync to Supabase
supabase_loader = SupabaseLeadLoader(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY")
)

# Sync all leads
supabase_loader.sync_from_apollo(apollo_loader)
```

---

## 🔧 Configuration Summary

### Quick Start (CSV Only)

1. Export CSV from Apollo.io
2. Update `.env`:
   ```env
   APOLLO_CSV_PATH="./your_leads.csv"
   LINKEDIN_EMAIL="your-linkedin-email"
   LINKEDIN_PASSWORD="your-linkedin-password"
   OPENAI_API_KEY="your-openai-key"
   SERPER_API_KEY="your-serper-key"
   ```
3. Run: `python main.py`

### Full Configuration (.env file)

```env
# OpenAI API KEY
OPENAI_API_KEY="your-openai-api-key"

# Serper API Key for search
SERPER_API_KEY="your-serper-api-key"

# LinkedIn credentials for linkedin-api package
LINKEDIN_EMAIL="your-linkedin-email@example.com"
LINKEDIN_PASSWORD="your-linkedin-password"

# Apollo.io configurations
APOLLO_API_KEY="your-apollo-api-key"
APOLLO_CSV_PATH="./leads.csv"

# Supabase (optional)
SUPABASE_URL=""
SUPABASE_KEY=""
SUPABASE_TABLE_NAME="leads"
```

---

## 📝 Lead Status Flow

The application tracks lead status through these stages:

1. **NEW** - Fresh leads to be contacted
2. **ATTEMPTED_TO_CONTACT** - Outreach attempted
3. **UNQUALIFIED** - Not a good fit

Status updates are:

- **CSV Mode**: Stored in memory (export updated CSV using `export_updated_csv()`)
- **API Mode**: Limited by Apollo API capabilities
- **Supabase Mode**: Persisted to database automatically

---

## 🧪 Testing Your Setup

### Test CSV Loading

```python
from src.tools.leads_loader.apollo import ApolloLeadLoader

loader = ApolloLeadLoader(csv_file_path="./leads.csv")
leads = loader.fetch_records(status_filter="NEW")
print(f"Loaded {len(leads)} leads")
for lead in leads[:3]:
    print(f"- {lead['Name']} ({lead['Email']})")
```

### Test API Loading

```python
from src.tools.leads_loader.apollo import ApolloLeadLoader

loader = ApolloLeadLoader(api_key="your-api-key")
leads = loader.fetch_records()
print(f"Fetched {len(leads)} leads from Apollo API")
```

### Test Supabase

```python
from src.tools.leads_loader.supabase_loader import SupabaseLeadLoader

loader = SupabaseLeadLoader(
    supabase_url="your-url",
    supabase_key="your-key"
)
leads = loader.fetch_records(status_filter="NEW")
print(f"Loaded {len(leads)} leads from Supabase")
```

---

## 🔍 Troubleshooting

### CSV File Not Found

```
❌ CSV file not found: ./leads.csv
```

**Solution**: Make sure the CSV file path in `.env` is correct and the file exists.

### LinkedIn API Authentication Failed

```
Error scraping LinkedIn with linkedin-api: ...
```

**Solution**:
1. Check your LinkedIn credentials in `.env`
2. Ensure you're not using 2FA on LinkedIn
3. Try logging in manually to verify credentials

### Apollo API Rate Limit

```
❌ Apollo API error: 429 - Rate limit exceeded
```

**Solution**:
- Wait before retrying
- Consider using CSV export instead
- Upgrade to Apollo paid plan for higher limits

### Supabase Connection Error

```
❌ Error fetching from Supabase: ...
```

**Solution**:
1. Verify `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
2. Check if table exists in Supabase dashboard
3. Verify network connectivity

---

## 📚 Additional Resources

- [Apollo.io API Documentation](https://apolloio.github.io/apollo-api-docs/)
- [Supabase Documentation](https://supabase.com/docs)
- [linkedin-api Package](https://github.com/tomquirk/linkedin-api)

---

## ✅ Next Steps

1. Choose your preferred lead source method
2. Update your `.env` file with credentials
3. Test with a small batch of leads first
4. Run the full automation with `python main.py`

Happy automating! 🚀
