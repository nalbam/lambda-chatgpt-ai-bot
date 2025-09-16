# lambda-chatgpt-ai-bot

안녕하세요! 저는 AI 어시스턴트입니다.
여러분의 질문에 답변하고 다양한 문제를 해결하는 데 도움을 드리기 위해 만들어졌습니다.
저는 AWS Lambda에서 구동되며, Slack API와 Python을 사용하여 구성되었습니다.
또한, OpenAI의 강력한 언어 모델을 기반으로 작동하고 있어 자연스러운 대화와 정확한 정보 제공이 가능합니다.
업무 효율성을 높이고, 복잡한 질문에도 신속하게 답변할 수 있도록 설계되었습니다.
언제든지 궁금한 점이 있거나 도움이 필요하시면 저를 찾아주세요!

![Chatgpt Bot](images/bot.png)

## Install

```bash
$ brew install python@3.12

$ npm install -g serverless@3.38.0

$ sls plugin install -n serverless-python-requirements
$ sls plugin install -n serverless-dotenv-plugin

$ python -m pip install --upgrade -r requirements.txt
```

## Setup

Setup a Slack app by following the guide at https://slack.dev/bolt-js/tutorial/getting-started

Set scopes to Bot Token Scopes in OAuth & Permission:

```
app_mentions:read
channels:history
channels:join
channels:read
chat:write
files:read
files:write
im:read
im:write
users:read
```

Set scopes in Event Subscriptions - Subscribe to bot events

```
app_mention
message.im
```

## Credentials

```bash
$ cp .env.example .env
```

### Slack Bot

```bash
SLACK_BOT_TOKEN="xoxb-xxxx"
SLACK_SIGNING_SECRET="xxxx"
```

### OpenAi API

* <https://platform.openai.com/account/api-keys>

```bash
OPENAI_ORG_ID="org-xxxx"
OPENAI_API_KEY="sk-xxxx"
```

## Deployment

In order to deploy the example, you need to run the following command:

```bash
$ sls deploy --region us-east-1
```

## Slack Test

```bash
curl -X POST -H "Content-Type: application/json" \
-d " \
{ \
    \"token\": \"Jhj5dZrVaK7ZwHHjRyZWjbDl\", \
    \"challenge\": \"3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P\", \
    \"type\": \"url_verification\" \
}" \
https://xxxx.execute-api.us-east-1.amazonaws.com/dev/slack/events
```

## OpenAi API Test

```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4.1",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant."
      },
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

```bash
curl https://api.openai.com/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "dall-e-3",
    "prompt": "꽁꽁 얼어붙은 한강위로 고양이가 걸어갑니다.",
    "size": "1024x1024",
    "n": 1
  }'
```

## References

* <https://github.com/openai/openai-python>
