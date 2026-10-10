## 1. Topic registry

- [x] 1.1 Add per-bot topic registry storage (centroid vector, label, atom_count, updated_at)
- [x] 1.2 Implement `assign_topic_key()` with regex-first, cluster-fallback in `topic_metadata.py`
- [x] 1.3 Config: `topic_cluster_enabled`, `topic_cluster_threshold`

## 2. Integration

- [x] 2.1 Hook topic assignment into L1 write path (`store_l1.py` / `l1_extractor.py`)
- [x] 2.2 Incremental centroid update on new atom
- [x] 2.3 Admin/rebuild: recompute centroids when embedding model changes

## 3. Tests & benchmark

- [x] 3.1 Unit tests: regex priority, cluster assign, new topic creation, embed off fallback
- [ ] 3.2 PersonaMem 200: evolution + reasons 分项对比
- [x] 3.3 Optional: memory browser show topic label
