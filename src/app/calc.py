# src/app/calc.py
#
# A deliberately tiny module — the pipeline is the real deliverable, not this code.
# These functions give lint, test, and build stages something real to exercise.


def add(a: int | float, b: int | float) -> int | float:
    """Return the sum of a and b."""
    return a + b


def subtract(a: int | float, b: int | float) -> int | float:
    """Return a minus b."""
    return a - b


def health() -> dict:
    """Return a simple health-check payload used by the post-deploy smoke test."""
    return {"status": "ok", "version": "0.1.0"}
