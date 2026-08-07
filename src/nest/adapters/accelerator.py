from __future__ import annotations

"""Accelerator resolver and guarded transformers MPS float32 patch.

This module centralizes device resolution for Docling usage and provides a
small guarded monkey-patch to disarm transformers' float64 positional
embedding on Apple MPS devices by forcing float32 only when the runtime
selects an MPS device.

Public API:
- resolve_accelerator(): returns one of "cpu", "cuda", "mps" based on
  environment (NEST_ACCELERATOR) and probe results.
- apply_guarded_mps_patch(): attempt to monkeypatch transformers.function if
  present; return True if patch applied or unnecessary, False if patch
  failed (caller may choose to exclude mps).

Design notes:
- Probing torch is wrapped in try/except so machines without torch/GPU
  support do not raise during import.
- NEST_ACCELERATOR supports: auto|cpu|cuda|mps
"""

from __future__ import annotations

import logging
import os
from typing import Callable

logger = logging.getLogger("nest.adapters.accelerator")

VALID_ENV = {"auto", "cpu", "cuda", "mps"}


def _safe_torch_probe(fn: Callable[[], bool]) -> bool:
    try:
        return bool(fn())
    except Exception:
        logger.debug("Torch probe raised; treating as unavailable", exc_info=True)
        return False


def apply_guarded_mps_patch() -> bool:
    """Attempt to monkeypatch transformers' 2D positional-embedding builder.

    Returns True if the patch was applied successfully or the target symbol
    cannot be found (no-op). Returns False if the patch attempt raised an
    unexpected exception.
    """
    try:
        import transformers

        target = getattr(transformers, "build_2d_sinusoidal_position_embedding", None)
        if target is None:
            # Older/newer transformers may not expose the helper at module top-level.
            # Try to locate in known modeling modules.
            try:
                from transformers.models.rt_detr_v2 import modeling_rt_detr_v2 as m

                target = getattr(m, "build_2d_sinusoidal_position_embedding", None)
            except Exception:
                target = None

        if target is None:
            logger.info("transformers build_2d_sinusoidal_position_embedding not found; skipping patch")
            return True

        # Create wrapper that forces float32 when device.type == 'mps'
        def _patched(*args, **kwargs):
            # The original helper may accept a device kwarg or expect a device
            # attribute on tensors; we defensively coerce any 'dtype' to float32
            # if running on MPS.
            device = kwargs.get("device") if "device" in kwargs else None
            # If device wasn't provided, try to inspect first arg(s)
            if device is None and args:
                # some callsites pass a tensor/Device as first arg; tolerate that
                device = getattr(args[-1], "device", None)

            # device may be a torch.device-like object
            try:
                device_type = getattr(device, "type", None)
            except Exception:
                device_type = None

            if device_type == "mps":
                # Force dtype=float32 for returned embedding construction
                kwargs["dtype"] = getattr(__import__("torch"), "float32")
            return target(*args, **kwargs)

        # Apply patch at module level where we found the target
        if hasattr(transformers, "build_2d_sinusoidal_position_embedding"):
            transformers.build_2d_sinusoidal_position_embedding = _patched
        else:
            # set on modeling module if found
            from transformers.models.rt_detr_v2 import modeling_rt_detr_v2 as m

            m.build_2d_sinusoidal_position_embedding = _patched

        logger.info("Applied guarded MPS float32 patch to transformers positional embedding")
        return True
    except Exception as exc:
        logger.warning("Failed to apply guarded MPS patch: %s", exc)
        logger.debug("Patch failure details", exc_info=True)
        return False


def _validate_env(value: str) -> str:
    if value not in VALID_ENV:
        raise ValueError(f"Invalid NEST_ACCELERATOR value: {value!r}; must be one of {sorted(list(VALID_ENV))}")
    return value


def resolve_accelerator() -> str:
    """Resolve accelerator device.

    Reads NEST_ACCELERATOR (auto|cpu|cuda|mps). In 'auto' mode the order is:
      - cuda (if torch.cuda.is_available())
      - mps (if torch.backends.mps.is_available() AND guarded patch applies)
      - cpu

    Any probe error treats the backend as unavailable.
    """
    env = os.environ.get("NEST_ACCELERATOR", "auto").lower()
    env = _validate_env(env)

    if env == "cpu":
        return "cpu"
    if env == "cuda":
        return "cuda"
    if env == "mps":
        return "mps"

    # auto
    # Probe cuda
    cuda_available = False
    try:
        import torch

        cuda_available = _safe_torch_probe(torch.cuda.is_available)
    except Exception:
        cuda_available = False

    if cuda_available:
        return "cuda"

    # Probe mps and attempt patch
    mps_available = False
    try:
        import torch

        mps_available = _safe_torch_probe(lambda: getattr(torch.backends, "mps", None) is not None and getattr(torch.backends.mps, "is_available", lambda: False)())
    except Exception:
        mps_available = False

    if mps_available:
        patched = apply_guarded_mps_patch()
        if patched:
            return "mps"
        logger.warning("MPS available but guarded patch failed; falling back to cpu")

    return "cpu"
