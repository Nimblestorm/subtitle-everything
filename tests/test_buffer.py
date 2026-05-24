import pytest
from buffer import SubtitleBuffer


def test_push_appends_line():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("hello")
    assert buf.get_lines() == ["hello"]


def test_push_multiple_lines():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("line one")
    buf.push("line two")
    assert buf.get_lines() == ["line one", "line two"]


def test_push_trims_to_max_lines():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("a")
    buf.push("b")
    buf.push("c")
    buf.push("d")
    assert buf.get_lines() == ["b", "c", "d"]


def test_get_lines_returns_copy():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("hello")
    lines = buf.get_lines()
    lines.append("injected")
    assert buf.get_lines() == ["hello"]


def test_clear_empties_buffer():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("hello")
    buf.clear()
    assert buf.get_lines() == []


def test_default_max_lines_is_three():
    buf = SubtitleBuffer()
    for i in range(5):
        buf.push(f"line {i}")
    assert len(buf.get_lines()) == 3


def test_max_lines_zero_raises():
    with pytest.raises(ValueError, match="max_lines must be >= 1"):
        SubtitleBuffer(max_lines=0)


def test_max_lines_one_overwrites_previous():
    buf = SubtitleBuffer(max_lines=1)
    buf.push("first")
    buf.push("second")
    assert buf.get_lines() == ["second"]


def test_push_after_clear_starts_fresh():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("old line")
    buf.clear()
    buf.push("new line")
    assert buf.get_lines() == ["new line"]
