# Required Image Descriptions Determine Document Success

When LLM image descriptions are enabled, a failed required description makes the document fail even if its text could be exported.
Treating such a run as successful with warnings would let automation accept incomplete context and let unchanged-file detection prevent retry.
Sync and convert return a nonzero exit code for these failures, retain previous successful outputs, and leave failed documents eligible for retry; extraction quality warnings remain distinct from failures.