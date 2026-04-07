"""Tests for handler.get_reactions and handler.conversations_replies."""

import handler


class TestGetReactions:
    """Tests for handler.get_reactions — formats reaction info as text."""

    def test_single_reaction_single_user(self, mock_app_client):
        mock_app_client.users_info.return_value = {
            "user": {"profile": {"display_name": "Alice"}}
        }
        reactions = [{"name": "thumbsup", "users": ["U_ALICE"]}]

        result = handler.get_reactions(reactions)

        assert ":thumbsup:" in result
        assert "Alice" in result
        mock_app_client.users_info.assert_called_once_with(user="U_ALICE")

    def test_multiple_reactions(self, mock_app_client):
        def users_info_dispatch(user):
            lookup = {
                "U_ALICE": {"user": {"profile": {"display_name": "Alice"}}},
                "U_BOB": {"user": {"profile": {"display_name": "Bob"}}},
            }
            return lookup.get(user, {"user": {"profile": {"display_name": "Unknown"}}})

        mock_app_client.users_info.side_effect = users_info_dispatch
        reactions = [
            {"name": "thumbsup", "users": ["U_ALICE"]},
            {"name": "heart", "users": ["U_BOB"]},
        ]

        result = handler.get_reactions(reactions)

        # Clean up side_effect so it does not leak to subsequent tests
        mock_app_client.users_info.side_effect = None

        assert ":thumbsup:" in result
        assert ":heart:" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_empty_reactions_returns_empty_string(self, mock_app_client):
        result = handler.get_reactions([])

        assert result == ""

    def test_exception_returns_empty_string(self, mock_app_client):
        # Pass a non-iterable to trigger an exception
        result = handler.get_reactions(None)

        assert result == ""


class TestConversationsReplies:
    """Tests for handler.conversations_replies — fetches thread history."""

    def test_empty_response_returns_empty_messages(self, mock_app_client):
        mock_app_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [],
        }

        result = handler.conversations_replies("C_CHAN", "1234.0000", "msg-001")

        assert result == []

    def test_skips_message_matching_client_msg_id(self, mock_app_client):
        # 3 messages: after reverse + pop(0), the latest (0003) is removed.
        # Remaining: [0002 (skip), 0001 (keep)]. 0002 matches client_msg_id so skipped.
        mock_app_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {"ts": "1234.0001", "text": "first", "user": "U1"},
                {"ts": "1234.0002", "text": "skip me", "user": "U2", "client_msg_id": "msg-001"},
                {"ts": "1234.0003", "text": "last", "user": "U3"},
            ],
        }

        result = handler.conversations_replies("C_CHAN", "1234.0000", "msg-001")

        # Only first msg should remain; skip-me was skipped by client_msg_id match
        assert len(result) == 1
        assert "first" in result[0]["content"]
        assert not any("skip me" in m["content"] for m in result)

    def test_bot_messages_get_assistant_role(self, mock_app_client):
        # After reverse + pop(0), the latest message (highest ts) is removed.
        # Place the bot message in the middle so it survives.
        mock_app_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {"ts": "1234.0001", "text": "first msg", "user": "U1"},
                {"ts": "1234.0002", "text": "bot reply", "bot_id": "B_BOT", "user": "U_BOT"},
                {"ts": "1234.0003", "text": "last msg", "user": "U_USER"},
            ],
        }

        result = handler.conversations_replies("C_CHAN", "1234.0000", "msg-999")

        bot_msgs = [m for m in result if m["role"] == "assistant"]
        assert len(bot_msgs) == 1
        assert "bot reply" in bot_msgs[0]["content"]

    def test_user_messages_get_user_role(self, mock_app_client):
        # Place the user reply in the middle so it is not popped.
        mock_app_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {"ts": "1234.0001", "text": "first msg", "user": "U1"},
                {"ts": "1234.0002", "text": "user reply", "user": "U_USER2"},
                {"ts": "1234.0003", "text": "last msg", "user": "U_USER3"},
            ],
        }

        result = handler.conversations_replies("C_CHAN", "1234.0000", "msg-999")

        user_msgs = [m for m in result if m["role"] == "user"]
        assert len(user_msgs) >= 1
        assert any("user reply" in m["content"] for m in user_msgs)

    def test_user_name_caching(self, mock_app_client):
        """Same user appears twice; users_info should be called only once for that user."""
        mock_app_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {"ts": "1234.0001", "text": "first msg", "user": "U1"},
                {"ts": "1234.0002", "text": "msg A", "user": "U_SAME"},
                {"ts": "1234.0003", "text": "msg B", "user": "U_SAME"},
                {"ts": "1234.0004", "text": "msg C", "user": "U_SAME"},
            ],
        }

        result = handler.conversations_replies("C_CHAN", "1234.0000", "msg-999")

        # After reverse + pop(0): first msg removed, 3 messages remain
        assert len(result) == 3
        # users_info called once for U_SAME (cached on subsequent calls)
        calls = [c for c in mock_app_client.users_info.call_args_list if c == ((), {"user": "U_SAME"})]
        assert len(calls) == 1

    def test_none_messages_initializes_to_empty_list(self, mock_app_client):
        mock_app_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [],
        }

        result = handler.conversations_replies("C_CHAN", "1234.0000", "msg-001", messages=None)

        assert isinstance(result, list)
        assert result == []

    def test_api_failure_returns_existing_messages(self, mock_app_client):
        mock_app_client.conversations_replies.side_effect = Exception("API error")
        existing = [{"role": "user", "content": "existing"}]

        result = handler.conversations_replies("C_CHAN", "1234.0000", "msg-001", messages=existing)

        assert result == existing
