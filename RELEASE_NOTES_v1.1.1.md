# v1.1.1 revision patch

- Treats non-uniquely invertible same-year day-1 Excel serial-date artefacts as unresolved rather than deterministically corrected.
- Emits `unresolved_source_artifacts_from_raw.csv`.
- Revised raw rebuild yields 59,670 records, 1,586 deterministic technical corrections, 22 unresolved source artefacts, 1,585 QC flags, and 1,973 zero-semantics review rows.
- Updates the SRC054 normalized-content fingerprint and publication-level canonical hash.
- Adds unit tests for ambiguity-safe serial handling.

Prepared in response to peer-review comments for ERC-106281.
