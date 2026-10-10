## 1. Schema & prompt

- [x] 1.1 Define L1 extraction JSON schema and validation helpers in `l1_extractor.py`
- [x] 1.2 Add structured extraction prompt template (fact/preference/constraint/todo + supersede hints)
- [x] 1.3 Add config `l1_extract_mode` with default `hybrid` in `config_store.py`

## 2. Write path

- [x] 2.1 Extend L1 frontmatter / index columns for subject, predicate, object (optional)
- [x] 2.2 Map `supersedes_hint` to existing supersede flow in `store_l1.py`
- [x] 2.3 Wire extraction role model from P3 `model_roles.extraction`

## 3. Fallback & limits

- [x] 3.1 Implement heuristic fallback on LLM failure with trace warning
- [x] 3.2 Enforce per-turn atom budget (default 5)
- [x] 3.3 Unit tests: valid JSON, invalid JSON fallback, supersede hint resolution

## 4. Benchmark

- [ ] 4.1 Run PersonaMem official 200 with structured extraction enabled
- [ ] 4.2 Compare vs P4 archived baseline on facts / evolution / recommendations
- [ ] 4.3 Record results as `report_l1_structured_200.json`
