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
