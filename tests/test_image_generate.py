"""Tests for handler.image_generate — image generation flow."""

from unittest.mock import MagicMock, patch

import handler


class TestImageGenerateSimple:
    """Simple image generation without thread or attached files."""

    def test_full_flow_no_thread_no_files(self, mock_say, mock_app_client, mock_openai):
        # Arrange
        content = [{"type": "text", "text": "a cute cat"}]
        channel = "C_CHAN"
        thread_ts = None
        client_msg_id = "msg-001"

        # Mock prompt preparation response
        mock_prep_response = MagicMock()
        mock_prep_response.choices = [MagicMock()]
        mock_prep_response.choices[0].message.content = "DALL-E prompt: a cute cat"
        mock_openai.chat.completions.create.return_value = mock_prep_response

        with patch.object(handler, "reply_image", return_value="https://img.url/cat.png") as mock_reply:
            # Act
            handler.image_generate(mock_say, thread_ts, content, channel, client_msg_id)

            # Assert — reply_image called with prepared prompt
            mock_reply.assert_called_once()
            assert mock_reply.call_args[0][0] == "DALL-E prompt: a cute cat"

    def test_initial_bot_cursor_posted(self, mock_say, mock_app_client, mock_openai):
        # Arrange
        content = [{"type": "text", "text": "draw something"}]

        mock_prep_response = MagicMock()
        mock_prep_response.choices = [MagicMock()]
        mock_prep_response.choices[0].message.content = "prompt"
        mock_openai.chat.completions.create.return_value = mock_prep_response

        with patch.object(handler, "reply_image", return_value="https://img.url/x.png"):
            # Act
            handler.image_generate(mock_say, None, content, "C_CHAN", "msg-001")

            # Assert — say() called first with BOT_CURSOR
            first_call = mock_say.call_args_list[0]
            assert first_call.kwargs["text"] == handler.BOT_CURSOR
            assert first_call.kwargs["thread_ts"] is None


class TestImageGenerateImmutability:
    """Verify that the original content list is not mutated."""

    def test_content_not_mutated_with_image_attachment(self, mock_say, mock_app_client, mock_openai):
        # Arrange — content with text + attached image
        original_text = "describe this 그려줘"
        content = [
            {"type": "text", "text": original_text},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
        ]

        # Mock describe response
        mock_describe_response = MagicMock()
        mock_describe_response.choices = [MagicMock()]
        mock_describe_response.choices[0].message.content = "A photo of a sunset"

        # Mock prompt preparation response
        mock_prep_response = MagicMock()
        mock_prep_response.choices = [MagicMock()]
        mock_prep_response.choices[0].message.content = "DALL-E prompt"

        mock_openai.chat.completions.create.side_effect = [
            mock_describe_response,
            mock_prep_response,
        ]

        with patch.object(handler, "reply_image", return_value="https://img.url/x.png"):
            # Act
            handler.image_generate(mock_say, None, content, "C_CHAN", "msg-001")

            # Assert — original content[0]["text"] unchanged
            assert content[0]["text"] == original_text


class TestImageGeneratePromptPreparationFailure:
    """When OpenAI prompt preparation raises, error message sent and early return."""

    def test_prompt_preparation_error_sends_message_and_returns(
        self, mock_say, mock_app_client, mock_openai
    ):
        # Arrange
        content = [{"type": "text", "text": "draw a dog"}]

        mock_openai.chat.completions.create.side_effect = Exception("API down")

        with patch.object(handler, "reply_image") as mock_reply:
            # Act
            handler.image_generate(mock_say, None, content, "C_CHAN", "msg-001")

            # Assert — reply_image never called (early return)
            mock_reply.assert_not_called()

            # Assert — chat_update called with error message
            update_calls = mock_app_client.chat_update.call_args_list
            last_update_text = update_calls[-1].kwargs.get(
                "text", update_calls[-1][1].get("text", "")
            )
            assert "오류" in last_update_text


class TestImageGenerateReplyImageFailure:
    """When reply_image raises, error message sent."""

    def test_image_generation_error_sends_message(
        self, mock_say, mock_app_client, mock_openai
    ):
        # Arrange
        content = [{"type": "text", "text": "draw a horse"}]

        mock_prep_response = MagicMock()
        mock_prep_response.choices = [MagicMock()]
        mock_prep_response.choices[0].message.content = "DALL-E prompt: horse"
        mock_openai.chat.completions.create.side_effect = None
        mock_openai.chat.completions.create.return_value = mock_prep_response

        with patch.object(handler, "reply_image", side_effect=Exception("Image gen failed")):
            # Act
            handler.image_generate(mock_say, None, content, "C_CHAN", "msg-001")

            # Assert — chat_update called with image generation error
            update_calls = mock_app_client.chat_update.call_args_list
            last_update_text = update_calls[-1].kwargs.get(
                "text", update_calls[-1][1].get("text", "")
            )
            assert "이미지 생성" in last_update_text


class TestImageGenerateWithThread:
    """When thread_ts is provided, conversations_replies is called."""

    def test_thread_fetches_replies(self, mock_say, mock_app_client, mock_openai):
        # Arrange
        content = [{"type": "text", "text": "draw more"}]
        thread_ts = "1111111111.000000"

        mock_prep_response = MagicMock()
        mock_prep_response.choices = [MagicMock()]
        mock_prep_response.choices[0].message.content = "DALL-E prompt"
        mock_openai.chat.completions.create.return_value = mock_prep_response

        mock_replies = [
            {"role": "user", "content": "draw a cat"},
            {"role": "assistant", "content": "here is a cat"},
        ]

        with (
            patch.object(handler, "reply_image", return_value="https://img.url/x.png"),
            patch.object(
                handler, "conversations_replies", return_value=mock_replies
            ) as mock_conv_replies,
        ):
            # Act
            handler.image_generate(
                mock_say, thread_ts, content, "C_CHAN", "msg-001", "image"
            )

            # Assert — conversations_replies called with correct args
            mock_conv_replies.assert_called_once_with(
                "C_CHAN", thread_ts, "msg-001", [], "image"
            )
