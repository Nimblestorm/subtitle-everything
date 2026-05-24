import threading


class SubtitleBuffer:
    def __init__(self, max_lines: int = 3):
        if max_lines < 1:
            raise ValueError(f"max_lines must be >= 1, got {max_lines!r}")
        self._lines: list[str] = []
        self._max_lines = max_lines
        self._lock = threading.Lock()

    def push(self, text: str) -> None:
        with self._lock:
            self._lines.append(text)
            if len(self._lines) > self._max_lines:
                self._lines = self._lines[-self._max_lines:]

    def get_lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def clear(self) -> None:
        with self._lock:
            self._lines = []
