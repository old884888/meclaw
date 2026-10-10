## ADDED Requirements

### Requirement: Embedding-based topic clustering

The system SHALL maintain per-bot topic centroids derived from L1 atom embeddings and SHALL assign new atoms to an existing topic when similarity exceeds a configured threshold, otherwise create a new topic key.

#### Scenario: Regex hint matches first

- **WHEN** L1 content matches a configured `TOPIC_KEY_HINTS` pattern
- **THEN** the atom SHALL use the regex-derived topic key
- **AND** clustering SHALL NOT override that assignment

#### Scenario: Cluster assigns existing topic

- **WHEN** no regex hint matches
- **AND** `topic_cluster_enabled` is true
- **AND** the atom embedding similarity to a centroid exceeds `topic_cluster_threshold`
- **THEN** the atom SHALL be assigned to that topic key
- **AND** the centroid SHALL be updated incrementally

#### Scenario: Cluster creates new topic

- **WHEN** no centroid exceeds the threshold
- **THEN** the system SHALL create a new topic key and centroid from the atom embedding
- **AND** SHALL store an optional human-readable label derived from atom content

#### Scenario: Embedding disabled

- **WHEN** `embedding_provider` is `off`
- **THEN** topic clustering SHALL be disabled
- **AND** topic assignment SHALL fall back to regex-only or `misc_<hash>` behavior
