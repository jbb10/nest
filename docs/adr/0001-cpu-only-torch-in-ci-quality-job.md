# CPU-only PyTorch in the CI quality job

The CI quality job (lint, format, typecheck, secret scan) never runs torch
inference, but it installs the full dependency tree because pyright needs every
package importable to resolve types. On Linux x86_64, PyTorch's PyPI wheel pulls
~1.8 GB of nvidia-CUDA transitive deps. We install CPU-only PyTorch instead,
using `UV_INDEX` (CPU PyTorch index) + `UV_DEFAULT_INDEX` (PyPI) +
`UV_INDEX_STRATEGY=unsafe-best-match` + `--upgrade-package torch` to force uv to
re-resolve torch against the CPU index, bypassing the lockfile's CUDA pin. This
drops the install from 37-107s to 8s with zero pyright errors.

## Considered Options

### Option A: cache the full wheel cache (remove `prune-cache: true`)

Rejected. The unpruned cache is 3.4 GB. Restoring it takes 54s, which costs as
much as re-downloading from PyPI (40s). It also consumes 1/3 of the 10 GB
GitHub Actions cache quota per OS. `prune-cache: true` remains the right default
for GitHub-hosted runners: re-downloading pre-built wheels from PyPI is faster
than restoring a multi-GB cache, and source-built wheels (which actually benefit
from caching) are retained.

### Option B (accepted): CPU-only PyTorch for the quality job

The quality job's transitive `torch` -> `nvidia-*-cu12` deps account for ~1.8 GB
of the ~2 GB total download. Switching to the CPU PyTorch wheel eliminates all
nvidia-CUDA deps while keeping every package pyright needs installed. Install
time drops to 8s. The test and e2e jobs keep the full CUDA torch because they
execute docling/torch code.

## Consequences

- The quality job uses `UV_FROZEN=0`, which means `uv run` (invoked by
  `make typecheck`) will not enforce the lockfile for that job. This is
  intentional: the venv intentionally diverges from the lockfile (CPU torch
  vs CUDA torch), and `UV_FROZEN=1` would cause `uv run` to re-sync back to
  the CUDA wheel.
- A separate `cache-suffix: lint` prevents the CPU-only cache from colliding
  with the test/e2e full-deps cache.
- The `--upgrade-package` flags cause uv to re-resolve torch, torchvision, and
  triton on every quality-job run (not read them from the lockfile). This adds
  ~1s of resolution time but is negligible compared to the 29-99s saved.
- If a future dependency pulls a different package from the CPU PyTorch index at
  an incompatible version, `UV_INDEX_STRATEGY=unsafe-best-match` will pick the
  best version across both indexes rather than failing.
