# LLM Provider Configuration Guide

This application now supports multiple LLM providers with **OpenAI as the default**. You can easily switch between OpenAI, Google Gemini, and Anthropic Claude.

## Quick Start (OpenAI - Default)

1. **Get your OpenAI API key** from https://platform.openai.com/api-keys

2. **Update your `.env` file**:
```env
LLM_PROVIDER="openai"
OPENAI_API_KEY="your-openai-api-key-here"
```

3. **Run the application**:
```bash
python main.py
```

That's it! The application will now use OpenAI's GPT-4o-mini by default.

## Switching to Google Gemini

If you prefer to use Google Gemini or need to switch back:

1. **Get your Gemini API key** from https://ai.google.dev/

2. **Update your `.env` file**:
```env
LLM_PROVIDER="google"
GOOGLE_API_KEY="your-gemini-api-key-here"
GEMINI_API_KEY="your-gemini-api-key-here"
```

3. **Run the application**:
```bash
python main.py
```

## Switching to Anthropic Claude

To use Anthropic's Claude models:

1. **Get your Anthropic API key** from https://console.anthropic.com/

2. **Update your `.env` file**:
```env
LLM_PROVIDER="anthropic"
ANTHROPIC_API_KEY="your-anthropic-api-key-here"
```

3. **Run the application**:
```bash
python main.py
```

## Available Models

### OpenAI (Default)
- **Default Model**: `gpt-4o-mini` (cost-efficient, fast)
- **Alternative**: `gpt-4o` (more powerful, higher cost)
- **Embeddings**: `text-embedding-3-small`

### Google Gemini
- **Default Model**: `gemini-2.0-flash-exp` (fast, efficient)
- **Alternative**: `gemini-2.0-flash-thinking-exp` (enhanced reasoning)
- **Embeddings**: `models/text-embedding-004`

### Anthropic Claude
- **Default Model**: `claude-3-5-sonnet-20241022`

## Custom Model Selection

You can override the default model in your code:

```python
from src.utils import invoke_llm

# Use specific OpenAI model
response = invoke_llm(
    system_prompt="You are a helpful assistant",
    user_message="Hello!",
    llm_provider="openai",
    model="gpt-4o"  # Override default
)

# Use specific Gemini model
response = invoke_llm(
    system_prompt="You are a helpful assistant",
    user_message="Hello!",
    llm_provider="google",
    model="gemini-2.0-flash-thinking-exp"
)
```

## Model Constants

The following constants are available in `src/utils.py`:

```python
# OpenAI
OPENAI_GPT4O_MODEL = "gpt-4o"
OPENAI_GPT4O_MINI_MODEL = "gpt-4o-mini"

# Google Gemini
GEMINI_FLASH_MODEL = "gemini-2.0-flash-exp"
GEMINI_PRO_MODEL = "gemini-2.0-flash-thinking-exp"
```

## Cost Considerations

### OpenAI Pricing (as of 2025)
- **gpt-4o-mini**: ~$0.15/1M input tokens, ~$0.60/1M output tokens (recommended default)
- **gpt-4o**: ~$2.50/1M input tokens, ~$10.00/1M output tokens

### Google Gemini Pricing
- **gemini-2.0-flash**: Free tier available, then paid tiers
- Check current pricing at https://ai.google.dev/pricing

### Anthropic Claude Pricing
- **claude-3-5-sonnet**: ~$3.00/1M input tokens, ~$15.00/1M output tokens

## Troubleshooting

### "Rate limit exceeded" or "Quota exceeded"

**For OpenAI:**
- Check your usage at https://platform.openai.com/usage
- Verify your billing settings
- Consider upgrading your plan

**For Google Gemini:**
- Check usage at https://ai.dev/usage?tab=rate-limit
- Verify API key permissions
- Switch to OpenAI as alternative

**Solution: Switch providers**
```env
# Simply change the provider in .env
LLM_PROVIDER="openai"  # or "google" or "anthropic"
```

### "Invalid API key"

1. Verify your API key is correctly copied (no extra spaces)
2. Check the key is active in your provider's dashboard
3. Ensure you've set the correct environment variable name

### "Module not found" errors

Install required dependencies:
```bash
pip install -r requirements.txt
```

## Environment Variables Reference

Copy `.env.example` to `.env` and configure:

```env
# LLM Provider (Required)
LLM_PROVIDER="openai"  # Options: "openai", "google", "anthropic"

# API Keys (Only the one matching your provider is required)
OPENAI_API_KEY="your-openai-key"
GOOGLE_API_KEY="your-gemini-key"
GEMINI_API_KEY="your-gemini-key"  # Same as GOOGLE_API_KEY
ANTHROPIC_API_KEY="your-anthropic-key"

# Other required keys
SERPER_API_KEY="your-serper-key"
RAPIDAPI_KEY="your-rapidapi-key"
```

## Migration from Gemini to OpenAI

If you were previously using Gemini and hitting quota limits:

1. **Get OpenAI API key** from https://platform.openai.com/api-keys

2. **Update `.env`**:
```env
LLM_PROVIDER="openai"
OPENAI_API_KEY="sk-..."
```

3. **Clear vector database** (if you want to rebuild with OpenAI embeddings):
```bash
rm -rf database/
```

4. **Run the application**:
```bash
python main.py
```

The application will automatically use OpenAI for both LLM and embeddings!

## Best Practices

1. **Start with OpenAI** - It's the default and well-supported
2. **Use environment variables** - Never hardcode API keys
3. **Monitor usage** - Check your provider's dashboard regularly
4. **Test with mini models** - Use `gpt-4o-mini` during development
5. **Keep backups** - Have API keys for multiple providers as fallbacks

## Support

For issues or questions:
- OpenAI: https://help.openai.com/
- Google Gemini: https://ai.google.dev/docs
- Anthropic: https://docs.anthropic.com/
