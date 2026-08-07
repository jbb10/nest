from __future__ import annotations

import os
from pathlib import Path

import pytest

from nest.adapters.accelerator import _validate_env, resolve_accelerator, apply_guarded_mps_patch


def test_validate_env_accepts_valid_values():
    for v in ("auto", "cpu", "cuda", "mps"):
        assert _validate_env(v) == v


def test_validate_env_rejects_invalid():
    with pytest.raises(ValueError):
        _validate_env("gut")


def test_resolve_accelerator_cpu_override(monkeypatch):
    monkeypatch.setenv("NEST_ACCELERATOR", "cpu")
    assert resolve_accelerator() == "cpu"


def test_resolve_accelerator_invalid_env(monkeypatch):
    monkeypatch.setenv("NEST_ACCELERATOR", "gut")
    with pytest.raises(ValueError):
        resolve_accelerator()


def test_apply_guarded_mps_patch_no_transformers(monkeypatch):
    # Simulate transformers not installed
    monkeypatch.setitem(sys.modules, "transformers", None)
    # Should return True (no-op)
    assert apply_guarded_mps_patch() is True
