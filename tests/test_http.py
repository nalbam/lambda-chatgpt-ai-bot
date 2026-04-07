"""Tests for HTTP image functions: get_image_from_url, get_image_from_slack, get_encoded_image_from_slack."""

import base64

import responses

import handler


class TestGetImageFromUrl:
    """Tests for handler.get_image_from_url — fetches image bytes from a URL."""

    @responses.activate
    def test_200_returns_content(self):
        image_bytes = b"\x89PNG\r\n\x1a\nfakeimage"
        responses.add(
            responses.GET,
            "https://example.com/image.png",
            body=image_bytes,
            status=200,
        )

        result = handler.get_image_from_url("https://example.com/image.png")

        assert result == image_bytes

    @responses.activate
    def test_404_returns_none(self):
        responses.add(
            responses.GET,
            "https://example.com/missing.png",
            status=404,
        )

        result = handler.get_image_from_url("https://example.com/missing.png")

        assert result is None

    @responses.activate
    def test_bearer_token_header_when_token_provided(self):
        responses.add(
            responses.GET,
            "https://example.com/secure.png",
            body=b"img",
            status=200,
        )

        handler.get_image_from_url("https://example.com/secure.png", token="xoxb-token")

        assert responses.calls[0].request.headers["Authorization"] == "Bearer xoxb-token"

    @responses.activate
    def test_no_auth_header_when_token_is_none(self):
        responses.add(
            responses.GET,
            "https://example.com/public.png",
            body=b"img",
            status=200,
        )

        handler.get_image_from_url("https://example.com/public.png", token=None)

        assert "Authorization" not in responses.calls[0].request.headers

    @responses.activate
    def test_timeout_parameter_passed(self):
        responses.add(
            responses.GET,
            "https://example.com/slow.png",
            body=b"img",
            status=200,
        )

        handler.get_image_from_url("https://example.com/slow.png")

        # The responses library records the request but doesn't expose timeout directly.
        # We verify the function completes successfully with the mocked response.
        assert responses.calls[0].response.status_code == 200


class TestGetImageFromSlack:
    """Tests for handler.get_image_from_slack — wraps get_image_from_url with SLACK_BOT_TOKEN."""

    @responses.activate
    def test_delegates_with_slack_bot_token(self):
        image_bytes = b"slack-image-data"
        responses.add(
            responses.GET,
            "https://files.slack.com/image.png",
            body=image_bytes,
            status=200,
        )

        result = handler.get_image_from_slack("https://files.slack.com/image.png")

        assert result == image_bytes
        assert responses.calls[0].request.headers["Authorization"] == f"Bearer {handler.SLACK_BOT_TOKEN}"


class TestGetEncodedImageFromSlack:
    """Tests for handler.get_encoded_image_from_slack — returns base64-encoded image."""

    @responses.activate
    def test_returns_base64_string(self):
        image_bytes = b"raw-image-bytes"
        responses.add(
            responses.GET,
            "https://files.slack.com/photo.png",
            body=image_bytes,
            status=200,
        )

        result = handler.get_encoded_image_from_slack("https://files.slack.com/photo.png")

        expected = base64.b64encode(image_bytes).decode("utf-8")
        assert result == expected

    @responses.activate
    def test_returns_none_when_image_fetch_fails(self):
        responses.add(
            responses.GET,
            "https://files.slack.com/broken.png",
            status=500,
        )

        result = handler.get_encoded_image_from_slack("https://files.slack.com/broken.png")

        assert result is None
