# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Slack bot powered by ChatGPT/OpenAI running on AWS Lambda. The bot responds to Slack mentions and direct messages, supports both text conversations and image generation (DALL-E).

## Common Development Commands

### Local Development

```bash
# Install dependencies
npm install
npm install -g serverless@3.38.0
sls plugin install -n serverless-python-requirements
sls plugin install -n serverless-dotenv-plugin
python -m pip install --upgrade -r requirements.txt

# Run tests (no test suite currently - manual testing via Slack)
# Test OpenAI API connection
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4.1", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Deployment

```bash
# Deploy to AWS Lambda (requires AWS credentials)
sls deploy --stage dev --region us-east-1

# Deploy to production
sls deploy --stage prod --region us-east-1
```

## Architecture

### Core Components

**handler.py** (664 lines) - Main Lambda function containing:
- Slack event handling via `slack_bolt` framework
- OpenAI API integration for chat and image generation
- DynamoDB integration for conversation history (1-hour TTL)
- Thread-based conversation tracking

### Key Functions Flow

1. **Slack Event Reception**: Lambda receives POST from Slack at `/slack/events`
2. **Message Processing**: `handle_app_mentions` or `handle_im` processes the message
3. **Context Management**: DynamoDB stores conversation history by thread/user
4. **AI Processing**:
   - Text: Sends conversation history to OpenAI chat completion
   - Images: Uses vision API for description, then DALL-E for generation
5. **Response**: Updates Slack thread with streaming-like updates

### Environment Variables

Critical configuration in `.env`:
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` - Slack authentication
- `OPENAI_API_KEY`, `OPENAI_ORG_ID` - OpenAI credentials
- `OPENAI_MODEL` (default: gpt-4.1) - Chat model selection
- `IMAGE_MODEL` (default: dall-e-3) - Image generation model
- `DYNAMODB_TABLE_NAME` - Conversation storage table

### AWS Resources

- **Lambda Function**: 5GB memory, 60s timeout
- **DynamoDB Table**: Stores conversation history with TTL
- **API Gateway**: Exposes Lambda via HTTP POST endpoint
- **IAM Role**: DynamoDB full access for conversation table

### Deployment Pipeline

GitHub Actions workflow (`.github/workflows/push-main.yml`):
- Triggers on push to main branch
- Uses OIDC for AWS authentication
- Deploys to `dev` stage by default
- Manages secrets via GitHub Secrets/Variables
