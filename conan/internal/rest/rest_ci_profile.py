"""Temporary timing for REST tests (remove when done debugging)."""
import sys


def log(message):
    print(f"[rest_api_test profile] {message}", file=sys.stderr, flush=True)
