"""Anthropic's usage fields do not mean what OpenAI's do.

OpenAI: input_tokens is the whole prompt; cached_tokens (in details) is the
part of it served from cache. Anthropic: input_tokens is only what was NOT
cached, with cache_read_input_tokens and cache_creation_input_tokens reported
alongside. Read Anthropic's input_tokens as a total and you get what
production showed — "24 tokens entrada (6122 en caché)", which the OpenAI
reading says is impossible and the Anthropic reading says is excellent.

Normalised here to one meaning: input = everything sent, cached = read from
cache, written = stored into cache (billed at a premium on Anthropic).
"""

from ..providers import parse_turn


def test_anthropic_input_is_the_sum_of_all_three_buckets() -> None:
    turn = parse_turn(
        "anthropic",
        {
            "content": [],
            "usage": {
                "input_tokens": 24,
                "cache_creation_input_tokens": 1200,
                "cache_read_input_tokens": 6122,
                "output_tokens": 622,
            },
        },
    )
    assert turn.input_tokens == 24 + 1200 + 6122
    assert turn.cached_tokens == 6122
    assert turn.cache_write_tokens == 1200
    assert turn.output_tokens == 622


def test_anthropic_without_cache_fields_is_just_input() -> None:
    turn = parse_turn("anthropic", {"content": [], "usage": {"input_tokens": 900}})
    assert turn.input_tokens == 900 and turn.cached_tokens == 0 and turn.cache_write_tokens == 0


def test_openai_semantics_are_unchanged() -> None:
    turn = parse_turn(
        "openai",
        {
            "output": [],
            "usage": {"input_tokens": 5000, "input_tokens_details": {"cached_tokens": 3200}},
        },
    )
    assert (
        turn.input_tokens == 5000 and turn.cached_tokens == 3200 and turn.cache_write_tokens == 0
    )


def test_openai_cache_writes_are_read_too() -> None:
    """OpenAI reports writes under input_tokens_details as well; same concept,
    same field on our side."""
    turn = parse_turn(
        "openai",
        {
            "output": [],
            "usage": {
                "input_tokens": 4400,
                "input_tokens_details": {"cached_tokens": 3584, "cache_write_tokens": 800},
            },
        },
    )
    assert turn.input_tokens == 4400
    assert turn.cached_tokens == 3584
    assert turn.cache_write_tokens == 800
