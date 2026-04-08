"""Temporary timing for REST tests (remove when done debugging)."""
import os
import sys
import time


def _github_summary_append(content: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            if sys.platform != "win32":
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(content)
                f.flush()
            finally:
                if sys.platform != "win32":
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def log(message: str) -> None:
    """Freeform line (auth deep timing, etc.); stderr + GitHub job summary bullet."""
    text = f"[rest_api_test profile] {message}"
    print(text, file=sys.stderr, flush=True)
    _github_summary_append(f"- {text}\n")


class RestApiProfile:
    """Segment timer for `TestRestApi` setup; stderr on each mark, table in finish()."""

    def __init__(self, summary_title: str = "`TestRestApi` setup timing"):
        self._summary_title = summary_title
        self._t0 = time.perf_counter()
        self._last = self._t0
        self._lines = []

    def mark(self, label: str) -> None:
        now = time.perf_counter()
        seg = now - self._last
        total = now - self._t0
        line = f"{label}: +{seg:.3f}s (total {total:.3f}s)"
        self._lines.append(line)
        msg = f"[rest_api_test profile] {line}"
        print(msg, file=sys.stderr, flush=True)

    def finish(self) -> None:
        if not self._lines:
            return
        parts = [f"### {self._summary_title}\n\n", "| Segment | Time |\n", "| --- | --- |\n"]
        for line in self._lines:
            cells = line.split(":", 1)
            if len(cells) == 2:
                parts.append(f"| {cells[0].strip()} | `{cells[1].strip()}` |\n")
            else:
                parts.append(f"| | `{line}` |\n")
        parts.append("\n")
        _github_summary_append("".join(parts))
