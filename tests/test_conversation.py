"""Tests for handler.conversation — orchestrates chat with OpenAI."""

from unittest.mock import patch, MagicMock

import handler


class TestConversation:
    """Tests for handler.conversation — builds message list and calls OpenAI."""

    @patch("handler.reply_text")
    @patch("handler.conversations_replies", return_value=[])
    def test_system_message_included_when_set(
        self, mock_conv_replies, mock_reply_text, mock_say, mock_app_client, mock_openai
    ):
        original = handler.SYSTEM_MESSAGE

        try:
            handler.SYSTEM_MESSAGE = "You are a test bot."

            handler.conversation(
                mock_say, "thread-1", "hello", "C_CHAN", "U_USER", "msg-001"
            )

            # Verify reply_text was called with messages starting with system message
            args = mock_reply_text.call_args[0]
            messages = args[0]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are a test bot."
        finally:
            handler.SYSTEM_MESSAGE = original

    @patch("handler.reply_text")
    @patch("handler.conversations_replies", return_value=[])
    def test_no_system_message_when_none(
        self, mock_conv_replies, mock_reply_text, mock_say, mock_app_client, mock_openai
    ):
        original = handler.SYSTEM_MESSAGE

        try:
            handler.SYSTEM_MESSAGE = None

            handler.conversation(
                mock_say, "thread-1", "hello", "C_CHAN", "U_USER", "msg-001"
            )

            args = mock_reply_text.call_args[0]
            messages = args[0]
            # No system message should be present
            assert all(m["role"] != "system" for m in messages)
        finally:
            handler.SYSTEM_MESSAGE = original

    @patch("handler.reply_text")
    @patch("handler.conversations_replies", return_value=[])
    def test_thread_mode_calls_conversations_replies(
        self, mock_conv_replies, mock_reply_text, mock_say, mock_app_client, mock_openai
    ):
        handler.conversation(
            mock_say, "thread-1", "hello", "C_CHAN", "U_USER", "msg-001"
        )

        mock_conv_replies.assert_called_once_with(
            "C_CHAN", "thread-1", "msg-001", [], None
        )

    @patch("handler.reply_text")
    @patch("handler.conversations_replies", return_value=[])
    def test_dm_mode_skips_conversations_replies(
        self, mock_conv_replies, mock_reply_text, mock_say, mock_app_client, mock_openai
    ):
        handler.conversation(
            mock_say, None, "hello", "C_CHAN", "U_USER", "msg-001"
        )

        mock_conv_replies.assert_not_called()

    @patch("handler.reply_text")
    @patch("handler.conversations_replies", return_value=[
        {"role": "user", "content": "TestUser: previous msg"}
    ])
    def test_user_content_is_last_in_messages(
        self, mock_conv_replies, mock_reply_text, mock_say, mock_app_client, mock_openai
    ):
        handler.conversation(
            mock_say, "thread-1", "my question", "C_CHAN", "U_USER", "msg-001"
        )

        args = mock_reply_text.call_args[0]
        messages = args[0]
        last = messages[-1]
        assert last["role"] == "user"
        assert last["content"] == "my question"

    @patch("handler.reply_text", side_effect=Exception("OpenAI timeout"))
    @patch("handler.conversations_replies", return_value=[])
    def test_openai_error_sends_error_message(
        self, mock_conv_replies, mock_reply_text, mock_say, mock_app_client, mock_openai
    ):
        handler.conversation(
            mock_say, "thread-1", "hello", "C_CHAN", "U_USER", "msg-001"
        )

        # chat_update is called with an error message
        mock_app_client.chat_update.assert_called()
        call_kwargs = mock_app_client.chat_update.call_args
        # The error message should be user-friendly Korean text
        error_text = call_kwargs[1].get("text", "") if call_kwargs[1] else call_kwargs[0][3]
        assert "오류" in error_text or "죄송" in error_text

    @patch("handler.reply_text")
    @patch("handler.conversations_replies", return_value=[])
    def test_initial_bot_cursor_posted_via_say(
        self, mock_conv_replies, mock_reply_text, mock_say, mock_app_client, mock_openai
    ):
        handler.conversation(
            mock_say, "thread-1", "hello", "C_CHAN", "U_USER", "msg-001"
        )

        mock_say.assert_called_once()
        call_kwargs = mock_say.call_args
        assert call_kwargs[1]["text"] == handler.BOT_CURSOR or call_kwargs[0][0] == handler.BOT_CURSOR
