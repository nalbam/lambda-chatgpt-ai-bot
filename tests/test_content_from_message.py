"""Tests for handler.content_from_message()."""

from unittest.mock import patch, MagicMock

import handler


KEYWORD_IMAGE = "그려줘"
KEYWORD_EMOJI = "이모지"


class TestMessageType:
    """Determine message_type based on prompt keywords."""

    def test_normal_text(self, mock_app_client):
        """Plain text prompt should return type 'text'."""
        content, msg_type = handler.content_from_message("Hello", {}, None)

        assert msg_type == "text"
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Hello"

    def test_ends_with_keyword_image(self, mock_app_client):
        """Prompt ending with KEYWORD_IMAGE should return type 'image'."""
        prompt = f"Draw a cat {KEYWORD_IMAGE}"
        content, msg_type = handler.content_from_message(prompt, {}, None)

        assert msg_type == "image"

    def test_ends_with_keyword_emoji(self, mock_app_client):
        """Prompt ending with KEYWORD_EMOJI should return type 'emoji'."""
        prompt = f"React with {KEYWORD_EMOJI}"
        content, msg_type = handler.content_from_message(prompt, {}, None)

        assert msg_type == "emoji"

    def test_starts_with_keyword_emoji(self, mock_app_client):
        """Prompt starting with KEYWORD_EMOJI should return type 'emoji'."""
        prompt = f"{KEYWORD_EMOJI} please"
        content, msg_type = handler.content_from_message(prompt, {}, None)

        assert msg_type == "emoji"

    def test_keyword_image_in_middle_only(self, mock_app_client):
        """Keyword in the middle (not at start/end) should NOT trigger."""
        prompt = f"I want {KEYWORD_IMAGE} now please"
        content, msg_type = handler.content_from_message(prompt, {}, None)

        assert msg_type == "text"

    def test_keyword_emoji_in_middle_only(self, mock_app_client):
        """KEYWORD_EMOJI in the middle only should be type 'text'."""
        prompt = f"Tell me about {KEYWORD_EMOJI} usage here"
        content, msg_type = handler.content_from_message(prompt, {}, None)

        assert msg_type == "text"


class TestUserInfo:
    """User display name prepended to text content."""

    def test_with_user_prepends_display_name(self, mock_app_client):
        """When user is provided, text should be 'DisplayName: prompt'."""
        content, msg_type = handler.content_from_message(
            "Hello", {}, user="U_USER",
        )

        mock_app_client.users_info.assert_called_once_with(user="U_USER")
        assert content[0]["text"] == "TestUser: Hello"

    def test_without_user_raw_prompt(self, mock_app_client):
        """When user is None, text should be the raw prompt."""
        content, msg_type = handler.content_from_message(
            "Hello", {}, user=None,
        )

        mock_app_client.users_info.assert_not_called()
        assert content[0]["text"] == "Hello"

    def test_user_with_missing_display_name(self, mock_app_client):
        """When display_name is missing, should fallback to 'Unknown'."""
        mock_app_client.users_info.return_value = {"user": {"profile": {}}}

        content, _ = handler.content_from_message(
            "Hi", {}, user="U_NO_NAME",
        )

        assert content[0]["text"] == "Unknown: Hi"


class TestImageAttachments:
    """Image file attachments in event produce image_url content blocks."""

    @patch("handler.get_encoded_image_from_slack")
    def test_single_image_file(self, mock_get_img, mock_app_client):
        """Event with one image file should add an image_url element."""
        mock_get_img.return_value = "base64data"

        event = {
            "files": [
                {
                    "mimetype": "image/png",
                    "url_private": "https://files.slack.com/img.png",
                }
            ]
        }

        content, msg_type = handler.content_from_message("Look", event, None)

        assert len(content) == 2
        assert content[1]["type"] == "image_url"
        assert "base64,base64data" in content[1]["image_url"]["url"]
        assert "image/png" in content[1]["image_url"]["url"]
        mock_get_img.assert_called_once_with("https://files.slack.com/img.png")

    @patch("handler.get_encoded_image_from_slack")
    def test_non_image_file_ignored(self, mock_get_img, mock_app_client):
        """Non-image files should not produce image_url elements."""
        event = {
            "files": [
                {
                    "mimetype": "application/pdf",
                    "url_private": "https://files.slack.com/doc.pdf",
                }
            ]
        }

        content, _ = handler.content_from_message("Check this", event, None)

        assert len(content) == 1  # only the text element
        mock_get_img.assert_not_called()

    @patch("handler.get_encoded_image_from_slack")
    def test_multiple_image_files(self, mock_get_img, mock_app_client):
        """Multiple image files should each produce an image_url element."""
        mock_get_img.return_value = "b64"

        event = {
            "files": [
                {"mimetype": "image/png", "url_private": "https://a.png"},
                {"mimetype": "image/jpeg", "url_private": "https://b.jpg"},
            ]
        }

        content, _ = handler.content_from_message("Two pics", event, None)

        assert len(content) == 3  # text + 2 images
        assert content[1]["type"] == "image_url"
        assert content[2]["type"] == "image_url"
        assert mock_get_img.call_count == 2

    @patch("handler.get_encoded_image_from_slack")
    def test_image_fetch_failure_no_image_url(self, mock_get_img, mock_app_client):
        """If image fetch returns None, no image_url should be appended."""
        mock_get_img.return_value = None

        event = {
            "files": [
                {"mimetype": "image/png", "url_private": "https://fail.png"},
            ]
        }

        content, _ = handler.content_from_message("Broken", event, None)

        assert len(content) == 1  # only text
        mock_get_img.assert_called_once()

    @patch("handler.get_encoded_image_from_slack")
    def test_mixed_files(self, mock_get_img, mock_app_client):
        """Mix of image and non-image files: only images processed."""
        mock_get_img.return_value = "b64"

        event = {
            "files": [
                {"mimetype": "image/gif", "url_private": "https://a.gif"},
                {"mimetype": "text/plain", "url_private": "https://b.txt"},
            ]
        }

        content, _ = handler.content_from_message("Mixed", event, None)

        assert len(content) == 2  # text + 1 image
        assert mock_get_img.call_count == 1

    def test_no_files_in_event(self, mock_app_client):
        """Event without files key should only have text content."""
        content, _ = handler.content_from_message("No files", {}, None)

        assert len(content) == 1
        assert content[0]["type"] == "text"
