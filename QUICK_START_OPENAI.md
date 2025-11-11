# Quick Start: Switch to OpenAI (3 Steps)

## Problem
Getting this error with Gemini?
```
ResourceExhausted: 429 You exceeded your current quota
```

## Solution: Switch to OpenAI (2 minutes)

### Step 1: Get OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-...`)

### Step 2: Update Your `.env` File

If you don't have a `.env` file, copy from the example:
```bash
cp .env.example .env
```

Then edit `.env` and add these two lines:
```env
LLM_PROVIDER="openai"
OPENAI_API_KEY="sk-your-actual-key-here"
```

### Step 3: Run Your Application
```bash
python main.py
```

**That's it!** Your application now uses OpenAI instead of Gemini.

---

## What Changed?

- **Before**: Used Google Gemini (hitting quota limits)
- **After**: Uses OpenAI GPT-4o-mini (faster, more reliable)
- **Embeddings**: Automatically switched to OpenAI embeddings too

## Want to Switch Back to Gemini Later?

Just change one line in `.env`:
```env
LLM_PROVIDER="google"
```

## Cost Information

**OpenAI GPT-4o-mini** (default model):
- Input: ~$0.15 per 1M tokens
- Output: ~$0.60 per 1M tokens
- Very affordable for most use cases

**Typical usage**: A single lead analysis costs ~$0.01-0.05

## Need Help?

See `LLM_SETUP.md` for detailed configuration options and troubleshooting.

## Verify It's Working

When you run the application, you should NOT see any Gemini errors. The application will use OpenAI seamlessly.

If you want to verify, check your OpenAI usage dashboard:
https://platform.openai.com/usage
