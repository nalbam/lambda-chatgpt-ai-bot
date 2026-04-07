"""
Test configuration — patches module-level side effects in handler.py
before it is imported. Must execute before any test file is collected.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# ── Step 1: Set required environment variables ──
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
os.environ.setdefault("OPENAI_ORG_ID", "org-test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("DYNAMODB_TABLE_NAME", "test-table")
os.environ.setdefault("OPENAI_MODEL", "gpt-test")
os.environ.setdefault("IMAGE_MODEL", "dall-e-test")
os.environ.setdefault("IMAGE_SIZE", "256x256")
os.environ.setdefault("SYSTEM_MESSAGE", "You are a test bot.")
os.environ.setdefault("MAX_LEN_SLACK", "3000")
os.environ.setdefault("MAX_LEN_OPENAI", "4000")
os.environ.setdefault("KEYWORD_IMAGE", "그려줘")
os.environ.setdefault("KEYWORD_EMOJI", "이모지")
os.environ.setdefault("BOT_CURSOR", ":robot_face:")

# ── Step 2: Create mock objects for module-level globals ──
mock_slack_app = MagicMock()
mock_slack_app.client.api_call.return_value = {"user_id": "U_TEST_BOT"}

mock_slack_handler = MagicMock()
mock_openai_client = MagicMock()
mock_table = MagicMock()
mock_dynamodb = MagicMock()
mock_dynamodb.Table.return_value = mock_table

# ── Step 3: Patch before import ──
_patches = [
    patch("slack_bolt.App", return_value=mock_slack_app),
    patch("slack_bolt.adapter.aws_lambda.SlackRequestHandler", return_value=mock_slack_handler),
    patch("boto3.resource", return_value=mock_dynamodb),
    patch("openai.OpenAI", return_value=mock_openai_client),
]

for p in _patches:
    p.start()

# NOW it is safe to import handler
import handler  # noqa: E402


# ── Step 4: Provide fixtures ──

@pytest.fixture
def mock_say():
    """Mock Slack say() function."""
    say = MagicMock()
    say.return_value = {"ts": "1234567890.000001"}
    return say


@pytest.fixture
def mock_app_client():
    """Reset and configure app.client mock for each test."""
    handler.app.client.reset_mock()
    handler.app.client.chat_update.return_value = {"ok": True}
    handler.app.client.api_call.return_value = {"user_id": "U_TEST_BOT"}
    handler.app.client.users_info.return_value = {
        "user": {"profile": {"display_name": "TestUser"}}
    }
    handler.app.client.conversations_replies.return_value = {
        "ok": True, "messages": []
    }
    handler.app.client.files_upload_v2.return_value = {"ok": True}
    return handler.app.client


@pytest.fixture
def mock_openai():
    """Reset and return the mock OpenAI client."""
    handler.openai.reset_mock()
    return handler.openai


@pytest.fixture
def mock_dynamo_table():
    """Reset and return the mock DynamoDB table."""
    handler.table.reset_mock()
    return handler.table


def make_lambda_event(body_dict):
    """Helper to create Lambda event payloads."""
    return {"body": json.dumps(body_dict)}


def make_slack_event(text="Hello", user="U_USER", channel="C_CHAN",
                     ts="1234567890.000000", thread_ts=None,
                     client_msg_id="msg-001", bot_id=None, files=None):
    """Helper to create Slack event bodies."""
    event = {
        "text": text,
        "user": user,
        "channel": channel,
        "ts": ts,
        "client_msg_id": client_msg_id,
    }
    if thread_ts:
        event["thread_ts"] = thread_ts
    if bot_id:
        event["bot_id"] = bot_id
    if files:
        event["files"] = files
    return {"event": event}
