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

# Run tests
pip install -r requirements-dev.txt
pytest -v

# Run tests with coverage
pytest --cov=handler --cov-report=term-missing
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

**handler.py** - Main Lambda function containing:
- Slack event handling via `slack_bolt` framework
- OpenAI API integration for chat and image generation
- DynamoDB integration for conversation history (1-hour TTL)
- Thread-based conversation tracking

### Key Functions Flow

1. **Slack Event Reception**: Lambda receives POST from Slack at `/slack/events`
2. **Message Processing**: `handle_mention` or `handle_message` processes the message
3. **Context Management**: DynamoDB stores conversation history by thread/user
4. **AI Processing**:
   - Text: Sends conversation history to OpenAI chat completion
   - Images: Uses vision API for description, then DALL-E for generation
5. **Response**: Updates Slack thread with streaming-like updates

### Environment Variables

Critical configuration in `.env`:
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` - Slack authentication
- `OPENAI_API_KEY`, `OPENAI_ORG_ID` - OpenAI credentials
- `OPENAI_MODEL` (default: gpt-5.4) - Chat model selection
- `IMAGE_MODEL` (default: gpt-image-1.5) - Image generation model
- `IMAGE_SIZE` (default: 1024x1024) - Generated image size
- `DYNAMODB_TABLE_NAME` - Conversation storage table
- `BOT_CURSOR` (default: :robot_face:) - Loading indicator emoji
- `SYSTEM_MESSAGE` (default: None) - Custom system prompt for AI
- `MAX_LEN_SLACK` (default: 3000) - Max Slack message length
- `MAX_LEN_OPENAI` (default: 4000) - Max OpenAI context length
- `KEYWORD_IMAGE` (default: 그려줘) - Keyword to trigger image generation
- `KEYWORD_EMOJI` (default: 이모지) - Keyword to trigger emoji reactions

### AWS Resources

- **Lambda Function**: 5GB memory, 60s timeout
- **DynamoDB Table**: Stores conversation history with TTL
- **API Gateway**: Exposes Lambda via HTTP POST endpoint
- **IAM Role**: DynamoDB full access for conversation table

### Deployment Pipeline

GitHub Actions workflow (`.github/workflows/push-main.yml`):
- Triggers on push to main branch or `repository_dispatch` event
- Uses OIDC for AWS authentication
- Deploys to `dev` stage by default
- Manages secrets via GitHub Secrets/Variables
