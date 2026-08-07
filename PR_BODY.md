Add NEST_ACCELERATOR resolver and guarded transformers MPS float32 patch.

- New: src/nest/adapters/accelerator.py
- Patch: src/nest/adapters/docling_processor.py to pass AcceleratorOptions(device=...)
- Tests: tests/adapters/test_accelerator.py

Fixes #3
