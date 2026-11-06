# 005 - Pending tasks

These tasks implement the parts of [spec 005](spec.md) that the code does not do yet.

- [ ] PM-007: Tag each Mem0 `add` and seed import with the source analysis date.
  Carry the date in snapshots, so `memories` becomes a list of text/date records.
  Replace the `n_matches` similarity search with a 100-candidate search, a recency
  rerank and a cap of 10 results.
- [ ] PM-008: When building seeds, drop source memories outside the lookback window.
- [ ] Add tests for A9 and A10, then update [evidence](evidence.md) when they pass.
