"""Tests for handler.handle_mention and handler.handle_message event handlers."""

from unittest.mock import MagicMock, patch

import handler
from tests.conftest import make_slack_event, mock_slack_app

# The @app.event decorator on a MagicMock app captures the original functions.
# Extract the real handle_mention and handle_message from the mock's call history.
_decorator_calls = mock_slack_app.event.return_value.call_args_list
_real_handle_mention = _decorator_calls[0][0][0]  # first decorator(fn) call
_real_handle_message = _decorator_calls[1][0][0]  # second decorator(fn) call


class TestHandleMention:
    """Tests for handler.handle_mention — Slack app_mention events."""

    def test_strips_bot_mention_from_text(self, mock_say, mock_app_client):
        # Arrange — text includes bot mention
        body = make_slack_event(text=f"<@{handler.bot_id}> hello world")

        with patch.object(handler, "conversation") as mock_conv:
            # Act
            _real_handle_mention(body, mock_say)

            # Assert — bot mention stripped, prompt is "hello world"
            call_args = mock_conv.call_args
            content_arg = call_args[0][2]  # 3rd positional: content
            assert "hello world" in content_arg[0]["text"]
            # Should NOT contain bot mention
            assert f"<@{handler.bot_id}>" not in content_arg[0]["text"]

    def test_routes_to_image_generate_for_image_type(self, mock_say, mock_app_client):
        # Arrange — text ends with image keyword
        keyword = handler.KEYWORD_IMAGE
        body = make_slack_event(text=f"<@{handler.bot_id}> a sunset {keyword}")

        with (
            patch.object(handler, "image_generate") as mock_img,
            patch.object(handler, "conversation") as mock_conv,
        ):
            # Act
            _real_handle_mention(body, mock_say)

            # Assert
            mock_img.assert_called_once()
            mock_conv.assert_not_called()

    def test_routes_to_conversation_for_text_type(self, mock_say, mock_app_client):
        # Arrange — plain text message
        body = make_slack_event(text=f"<@{handler.bot_id}> what is AI?")

        with (
            patch.object(handler, "image_generate") as mock_img,
            patch.object(handler, "conversation") as mock_conv,
        ):
            # Act
            _real_handle_mention(body, mock_say)

            # Assert
            mock_conv.assert_called_once()
            mock_img.assert_not_called()

    def test_uses_thread_ts_when_present(self, mock_say, mock_app_client):
        # Arrange — event has thread_ts
        body = make_slack_event(
            text=f"<@{handler.bot_id}> reply in thread",
            thread_ts="9999999999.000000",
            ts="1234567890.000000",
        )

        with patch.object(handler, "conversation") as mock_conv:
            # Act
            _real_handle_mention(body, mock_say)

            # Assert — thread_ts used instead of ts
            call_args = mock_conv.call_args
            thread_ts_arg = call_args[0][1]  # 2nd positional: thread_ts
            assert thread_ts_arg == "9999999999.000000"

    def test_falls_back_to_ts_when_no_thread_ts(self, mock_say, mock_app_client):
        # Arrange — event without thread_ts
        body = make_slack_event(
            text=f"<@{handler.bot_id}> new message",
            ts="1234567890.000000",
        )

        with patch.object(handler, "conversation") as mock_conv:
            # Act
            _real_handle_mention(body, mock_say)

            # Assert — ts used as thread_ts
            call_args = mock_conv.call_args
            thread_ts_arg = call_args[0][1]
            assert thread_ts_arg == "1234567890.000000"


class TestHandleMessage:
    """Tests for handler.handle_message — Slack DM events."""

    def test_ignores_bot_messages(self, mock_say, mock_app_client):
        # Arrange — event has bot_id
        body = make_slack_event(text="bot echo", bot_id="B_BOT")

        with (
            patch.object(handler, "conversation") as mock_conv,
            patch.object(handler, "image_generate") as mock_img,
        ):
            # Act
            _real_handle_message(body, mock_say)

            # Assert — no processing
            mock_conv.assert_not_called()
            mock_img.assert_not_called()

    def test_routes_dm_to_conversation_for_text(self, mock_say, mock_app_client):
        # Arrange — normal DM text
        body = make_slack_event(text="tell me a joke")

        with (
            patch.object(handler, "conversation") as mock_conv,
            patch.object(handler, "image_generate") as mock_img,
        ):
            # Act
            _real_handle_message(body, mock_say)

            # Assert
            mock_conv.assert_called_once()
            mock_img.assert_not_called()

    def test_routes_dm_to_image_generate_for_image_keyword(self, mock_say, mock_app_client):
        # Arrange — text ends with image keyword
        keyword = handler.KEYWORD_IMAGE
        body = make_slack_event(text=f"a mountain {keyword}")

        with (
            patch.object(handler, "conversation") as mock_conv,
            patch.object(handler, "image_generate") as mock_img,
        ):
            # Act
            _real_handle_message(body, mock_say)

            # Assert
            mock_img.assert_called_once()
            mock_conv.assert_not_called()

    def test_thread_ts_is_always_none_for_dm(self, mock_say, mock_app_client):
        # Arrange
        body = make_slack_event(text="hello from DM")

        with patch.object(handler, "conversation") as mock_conv:
            # Act
            _real_handle_message(body, mock_say)

            # Assert — thread_ts (2nd positional arg) is None
            call_args = mock_conv.call_args
            thread_ts_arg = call_args[0][1]
            assert thread_ts_arg is None

    def test_dm_image_thread_ts_is_none(self, mock_say, mock_app_client):
        # Arrange — image request in DM
        keyword = handler.KEYWORD_IMAGE
        body = make_slack_event(text=f"sunset {keyword}")

        with patch.object(handler, "image_generate") as mock_img:
            # Act
            _real_handle_message(body, mock_say)

            # Assert — thread_ts (2nd positional arg) is None
            call_args = mock_img.call_args
            thread_ts_arg = call_args[0][1]
            assert thread_ts_arg is None
