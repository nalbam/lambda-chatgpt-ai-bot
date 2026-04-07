"""Tests for handler.chat_update()."""

import handler


class TestChatUpdateShortMessage:
    """Short messages (len <= MAX_LEN_SLACK) — no splitting."""

    def test_short_message_no_continue(self, mock_say, mock_app_client):
        """Short message without continue_thread should update in place."""
        msg, ts = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message="Hello world", continue_thread=False,
        )

        mock_app_client.chat_update.assert_called_once_with(
            channel="C_CHAN", ts="ts-1", text="Hello world",
        )
        mock_say.assert_not_called()
        assert msg == "Hello world"
        assert ts == "ts-1"

    def test_short_message_with_continue(self, mock_say, mock_app_client):
        """Short message with continue_thread should append BOT_CURSOR."""
        msg, ts = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message="Hello", continue_thread=True,
        )

        mock_app_client.chat_update.assert_called_once_with(
            channel="C_CHAN", ts="ts-1",
            text="Hello " + handler.BOT_CURSOR,
        )
        mock_say.assert_not_called()
        assert msg == "Hello"
        assert ts == "ts-1"

    def test_empty_message(self, mock_say, mock_app_client):
        """Empty message should be treated as short (no split)."""
        msg, ts = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message="", continue_thread=False,
        )

        mock_app_client.chat_update.assert_called_once_with(
            channel="C_CHAN", ts="ts-1", text="",
        )
        mock_say.assert_not_called()
        assert msg == ""
        assert ts == "ts-1"

    def test_replace_text_applied_short(self, mock_say, mock_app_client):
        """Double asterisks should be replaced with single (CONVERSION_ARRAY)."""
        msg, ts = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message="**bold**", continue_thread=False,
        )

        mock_app_client.chat_update.assert_called_once_with(
            channel="C_CHAN", ts="ts-1", text="*bold*",
        )

    def test_returns_tuple(self, mock_say, mock_app_client):
        """Return value is always (message, latest_ts)."""
        result = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message="ok", continue_thread=False,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestChatUpdateLongMessageNewlineDelimiter:
    """Long messages split on '\\n\\n' delimiter."""

    def _make_long_message_even_parts(self):
        """Build a message with even number of parts after split on \\n\\n."""
        # 4 parts -> pop last -> 3 parts (odd) -> odd branch
        # We need even remaining parts: 3 parts total -> pop -> 2 remaining (even)
        part = "A" * 1000
        # 3 parts: split produces 3, pop -> 2 remaining (even)
        return f"{part}\n\n{part}\n\n{part}"

    def _make_long_message_odd_parts(self):
        """Build a message with odd number of remaining parts after pop."""
        part = "A" * 800
        # 4 parts: split produces 4, pop -> 3 remaining (odd)
        return f"{part}\n\n{part}\n\n{part}\n\n{part}"

    def test_even_parts_split(self, mock_say, mock_app_client):
        """Even remaining parts: text = join(parts) + split_key, message = last."""
        message = self._make_long_message_even_parts()
        parts = message.split("\n\n")
        assert len(parts) == 3  # after pop -> 2 (even)

        mock_say.return_value = {"ts": "new-ts"}
        msg, ts = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message=message, continue_thread=False,
        )

        # chat_update called for the first chunk
        mock_app_client.chat_update.assert_called_once()
        # say called for the continuation
        mock_say.assert_called_once()
        assert ts == "new-ts"

    def test_odd_parts_split(self, mock_say, mock_app_client):
        """Odd remaining parts: text = join(parts), message = split_key + last."""
        message = self._make_long_message_odd_parts()
        parts = message.split("\n\n")
        assert len(parts) == 4  # after pop -> 3 (odd)

        mock_say.return_value = {"ts": "new-ts-2"}
        msg, ts = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message=message, continue_thread=False,
        )

        mock_app_client.chat_update.assert_called_once()
        mock_say.assert_called_once()
        assert ts == "new-ts-2"

    def test_continue_thread_appends_cursor(self, mock_say, mock_app_client):
        """When continue_thread=True, the continuation gets BOT_CURSOR."""
        message = self._make_long_message_even_parts()
        mock_say.return_value = {"ts": "new-ts"}

        handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message=message, continue_thread=True,
        )

        # The say() call should include BOT_CURSOR
        say_call = mock_say.call_args
        assert handler.BOT_CURSOR in say_call.kwargs["text"]

    def test_say_called_with_thread_ts(self, mock_say, mock_app_client):
        """say() should be called with the original thread_ts."""
        message = self._make_long_message_even_parts()
        mock_say.return_value = {"ts": "new-ts"}

        handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message=message, continue_thread=False,
        )

        say_call = mock_say.call_args
        assert say_call.kwargs["thread_ts"] == "thread-1"


class TestChatUpdateLongMessageCodeBlockDelimiter:
    """Long messages split on '```' delimiter when code blocks present."""

    def test_code_block_split(self, mock_say, mock_app_client):
        """Messages with ``` should use that as the split key."""
        # Build: text```code```more  (3 parts, pop -> 2 even)
        code_block = "x" * 3000
        message = f"Here is code:```{code_block}```And the end."
        assert len(message) > handler.MAX_LEN_SLACK

        mock_say.return_value = {"ts": "code-ts"}
        msg, ts = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message=message, continue_thread=False,
        )

        mock_app_client.chat_update.assert_called_once()
        mock_say.assert_called_once()
        assert ts == "code-ts"


class TestChatUpdateLongMessageNoDelimiter:
    """Long messages with no \\n\\n or ``` — forced split at MAX_LEN_SLACK."""

    def test_forced_split(self, mock_say, mock_app_client):
        """No delimiter produces 1 part -> fallback: slice at MAX_LEN_SLACK."""
        message = "A" * 4000  # > 3000, no \n\n or ```
        mock_say.return_value = {"ts": "forced-ts"}

        msg, ts = handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message=message, continue_thread=False,
        )

        # First chunk updated via chat_update
        update_call = mock_app_client.chat_update.call_args
        first_text = update_call.kwargs["text"]
        assert len(first_text) == handler.MAX_LEN_SLACK

        # Remainder sent via say()
        mock_say.assert_called_once()
        say_text = mock_say.call_args.kwargs["text"]
        assert len(say_text) == 1000  # 4000 - 3000

        assert ts == "forced-ts"

    def test_forced_split_with_continue(self, mock_say, mock_app_client):
        """Forced split + continue_thread appends cursor to remainder."""
        message = "B" * 4000
        mock_say.return_value = {"ts": "forced-ts-2"}

        handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message=message, continue_thread=True,
        )

        say_text = mock_say.call_args.kwargs["text"]
        assert say_text.endswith(handler.BOT_CURSOR)


class TestChatUpdateReplaceText:
    """Verify replace_text is applied to both split and non-split paths."""

    def test_replace_text_in_split_first_chunk(self, mock_say, mock_app_client):
        """First chunk of a split message should have replace_text applied."""
        # Create long message with ** in the first part
        first_part = "**bold**" + "A" * 2000
        second_part = "B" * 1500
        message = f"{first_part}\n\n{second_part}"
        assert len(message) > handler.MAX_LEN_SLACK

        mock_say.return_value = {"ts": "rep-ts"}
        handler.chat_update(
            mock_say, "C_CHAN", "thread-1", "ts-1",
            message=message, continue_thread=False,
        )

        update_text = mock_app_client.chat_update.call_args.kwargs["text"]
        # ** should be replaced with *
        assert "**" not in update_text
