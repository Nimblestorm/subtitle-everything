class SubtitleBuffer:
    def __init__(self, max_lines: int = 3):
        self._lines: list[str] = []
        self._max_lines = max_lines

    def push(self, text: str) -> None:
        self._lines.append(text)
        if len(self._lines) > self._max_lines:
            self._lines = self._lines[-self._max_lines:]

    def get_lines(self) -> list[str]:
        return list(self._lines)

    def clear(self) -> None:
        self._lines = []
