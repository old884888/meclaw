## 1. L1 质量元数据

- [x] 1.1 `store_l1.py`：importance / hit_count / supersedes_id / superseded_by 读写
- [x] 1.2 `default_importance(type)` + enrich_atom 回填
- [x] 1.3 `update_atom_meta` / `increment_hit_count` / `mark_superseded`
- [x] 1.4 单测：switch 写入产生 supersede 链

## 2. 写入去重与冲突

- [x] 2.1 `memory_dedupe.py`：同 topic embedding 近似去重
- [x] 2.2 `write_atom` 集成 supersede + 去重
- [x] 2.3 `l1_extractor` heuristic/LLM 路径调用新 write 逻辑
- [x] 2.4 单测：高相似 duplicate 跳过（via dedupe helper + exact dedupe）

## 3. 复合召回排序

- [x] 3.1 新增 `memory_scoring.py`：recency / composite score
- [x] 3.2 `hybrid.py`：合并后 composite rerank；过滤 superseded hits
- [x] 3.3 `config_store.py`：权重与 half_life / dedupe_threshold
- [x] 3.4 单测：importance + recency 改变排序

## 4. 巩固与 LLM 提取

- [x] 4.1 `memory_brain.before_chat`：注入后 increment_hit_count
- [x] 4.2 `extract_atoms_llm` 结构化 prompt（topic_key / reason）
- [x] 4.3 单测：hit_count 递增

## 5. 文档

- [x] 5.1 更新 `超级大脑增强路线.md` §P4
- [x] 5.2 README 补充 memory quality 配置说明
