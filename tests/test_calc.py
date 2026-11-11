# tests/test_calc.py
#
# Unit tests for src/app/calc.py — executed by `pytest` in the CI pipeline.
# Keeping tests minimal so the focus stays on the pipeline mechanics.

import pytest

from app.calc import add, health, subtract


class TestAdd:
    def test_add_integers(self):
        assert add(2, 3) == 5

    def test_add_floats(self):
        assert add(1.5, 2.5) == pytest.approx(4.0)

    def test_add_negative(self):
        assert add(-1, 1) == 0


class TestSubtract:
    def test_subtract_basic(self):
        assert subtract(10, 3) == 7

    def test_subtract_to_negative(self):
        assert subtract(0, 5) == -5


class TestHealth:
    def test_health_returns_ok(self):
        result = health()
        assert result["status"] == "ok"

    def test_health_has_version(self):
        result = health()
        assert "version" in result
