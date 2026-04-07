"""Tests for handler.lambda_handler — Lambda entry point."""

import json
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError

import handler
from tests.conftest import make_lambda_event


class TestLambdaHandlerChallenge:
    """Slack Event Subscription challenge verification."""

    def test_challenge_response(self):
        # Arrange
        event = make_lambda_event({"challenge": "abc123"})

        # Act
        result = handler.lambda_handler(event, {})

        # Assert
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["challenge"] == "abc123"


class TestLambdaHandlerEarlyReturn:
    """Cases where lambda_handler returns 200 without processing."""

    def test_no_event_returns_200(self):
        # Arrange
        event = make_lambda_event({"type": "some_other_type"})

        # Act
        result = handler.lambda_handler(event, {})

        # Assert
        assert result["statusCode"] == 200

    def test_no_client_msg_id_returns_200(self):
        # Arrange
        event = make_lambda_event({
            "event": {"text": "hello", "user": "U_USER", "channel": "C_CHAN"}
        })

        # Act
        result = handler.lambda_handler(event, {})

        # Assert
        assert result["statusCode"] == 200


class TestLambdaHandlerDeduplication:
    """DynamoDB conditional write for duplicate execution prevention."""

    def test_first_message_accepted(self, mock_dynamo_table):
        # Arrange: put_item succeeds (no exception)
        mock_dynamo_table.put_item.return_value = {}
        event = make_lambda_event({
            "event": {
                "text": "hello",
                "user": "U_USER",
                "channel": "C_CHAN",
                "client_msg_id": "msg-unique-001",
            }
        })

        # Act
        with patch.object(handler.handler, "handle", return_value={"statusCode": 200}) as mock_handle:
            result = handler.lambda_handler(event, {})

        # Assert
        mock_dynamo_table.put_item.assert_called_once()
        call_kwargs = mock_dynamo_table.put_item.call_args[1]
        assert call_kwargs["Item"]["id"] == "msg-unique-001"
        assert call_kwargs["ConditionExpression"] == "attribute_not_exists(id)"
        mock_handle.assert_called_once_with(event, {})
        assert result["statusCode"] == 200

    def test_duplicate_message_rejected(self, mock_dynamo_table):
        # Arrange: put_item raises ConditionalCheckFailedException
        error_response = {
            "Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}
        }
        mock_dynamo_table.put_item.side_effect = ClientError(
            error_response, "PutItem"
        )
        event = make_lambda_event({
            "event": {
                "text": "hello",
                "user": "U_USER",
                "channel": "C_CHAN",
                "client_msg_id": "msg-dup-001",
            }
        })

        # Act
        with patch.object(handler.handler, "handle") as mock_handle:
            result = handler.lambda_handler(event, {})

        # Assert
        assert result["statusCode"] == 200
        mock_handle.assert_not_called()

    def test_unexpected_error_reraises(self, mock_dynamo_table):
        # Arrange: put_item raises a different ClientError
        error_response = {
            "Error": {"Code": "InternalServerError", "Message": "something broke"}
        }
        mock_dynamo_table.put_item.side_effect = ClientError(
            error_response, "PutItem"
        )
        event = make_lambda_event({
            "event": {
                "text": "hello",
                "user": "U_USER",
                "channel": "C_CHAN",
                "client_msg_id": "msg-err-001",
            }
        })

        # Act & Assert
        import pytest

        with pytest.raises(ClientError) as exc_info:
            handler.lambda_handler(event, {})

        assert exc_info.value.response["Error"]["Code"] == "InternalServerError"
