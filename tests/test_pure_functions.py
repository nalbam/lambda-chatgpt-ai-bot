"""Tests for pure text-processing functions: replace_text and replace_emoji_pattern."""

import handler


class TestReplaceText:
    """Tests for handler.replace_text — applies CONVERSION_ARRAY substitutions."""

    def test_bold_double_asterisks_converted_to_single(self):
        result = handler.replace_text("**bold**")
        assert result == "*bold*"

    def test_empty_string_returns_empty(self):
        result = handler.replace_text("")
        assert result == ""

    def test_single_asterisk_unchanged(self):
        result = handler.replace_text("*italic*")
        assert result == "*italic*"

    def test_multiple_bold_segments(self):
        result = handler.replace_text("**hello** and **world**")
        assert result == "*hello* and *world*"

    def test_plain_text_without_asterisks(self):
        result = handler.replace_text("no formatting here")
        assert result == "no formatting here"

    def test_triple_asterisks_partially_replaced(self):
        # *** -> after replacing ** with *, becomes *+remaining *
        result = handler.replace_text("***bold italic***")
        # "***" = "**" + "*" -> "*" + "*" = "**" (after replacement)
        assert result == "**bold italic**"

    def test_consecutive_double_asterisks(self):
        result = handler.replace_text("****")
        # "****" -> replace "**" twice -> "**"
        assert result == "**"


class TestReplaceEmojiPattern:
    """Tests for handler.replace_emoji_pattern — strips variant suffixes from emoji codes."""

    def test_standard_emoji_with_variant(self):
        result = handler.replace_emoji_pattern(":smile:variant:")
        assert result == ":smile:"

    def test_no_match_plain_text(self):
        result = handler.replace_emoji_pattern("hello world")
        assert result == "hello world"

    def test_no_match_single_colon_emoji(self):
        result = handler.replace_emoji_pattern(":smile:")
        assert result == ":smile:"

    def test_multiple_patterns_in_text(self):
        result = handler.replace_emoji_pattern(":wave:skin-tone-3: hi :thumbsup:skin-tone-2:")
        assert result == ":wave: hi :thumbsup:"

    def test_empty_string(self):
        result = handler.replace_emoji_pattern("")
        assert result == ""

    def test_slack_skin_tone_variant_adjacent_colons(self):
        # ":thumbsup::skin-tone-2:" has adjacent colons — the regex requires
        # :group1:group2: with no extra colons, so this does NOT match.
        result = handler.replace_emoji_pattern(":thumbsup::skin-tone-2:")
        assert result == ":thumbsup::skin-tone-2:"

    def test_slack_skin_tone_variant_without_extra_colon(self):
        # When the variant is written as :thumbsup:skin-tone-2: it matches.
        result = handler.replace_emoji_pattern(":thumbsup:skin-tone-2:")
        assert result == ":thumbsup:"

    def test_mixed_text_and_emoji(self):
        result = handler.replace_emoji_pattern("Hello :wave:skin-tone-4: World")
        assert result == "Hello :wave: World"

    def test_pattern_preserves_surrounding_text(self):
        result = handler.replace_emoji_pattern("before :emoji:variant: after")
        assert result == "before :emoji: after"
