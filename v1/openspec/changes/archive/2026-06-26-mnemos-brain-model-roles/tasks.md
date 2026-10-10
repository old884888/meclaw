## 1. 配置结构

- [x] 1.1 `config_store.py` 新增 `model_roles` 全局结构（executor/extraction/summary/embedding/rerank）
- [x] 1.2 Bot 级 `brains.model_roles` 覆盖结构 + 合并（复用 `brains_config_for_bot` 模式）
- [x] 1.3 归一：空值表示继承/回退；保留旧 `background_model` 兼容读取
- [x] 1.4 单测：默认全空、Bot 覆盖、与旧 background 并存

## 2. 角色解析器

- [x] 2.1 新增 `resolve_model(bot, role)`（集中于 `main.py` 或 `model_roles.py`）
- [x] 2.2 实现回退链：extraction/summary → background → executor；executor 必有
- [x] 2.3 embedding/rerank：无实现时返回 disabled 语义
- [x] 2.4 用解析器替换现有 `_profile_for_bot(role="executor"/"background")` 调用点（保持兼容）
- [x] 2.5 单测：继承/覆盖/回退矩阵，未配置时与现状等价

## 3. 后台任务接入

- [x] 3.1 `l1_extractor` 取 `extraction` 角色模型
- [x] 3.2 `tier3_summarizer` 取 `summary` 角色模型
- [x] 3.3 解析失败/无模型时按 job 状态跳过降级，不阻断聊天
- [x] 3.4 单测：提取/摘要按角色取模型；缺失走回退

## 4. UI 与状态

- [x] 4.1 Bot 编辑器「大脑」区新增「模型角色」分组（executor/extraction/summary 三下拉，留空继承）
- [x] 4.2 `app.js` 读写 `model_roles` 覆盖
- [x] 4.3 `brain_status.py` + 状态面板展示各角色实际解析到的模型
- [x] 4.4 前端联调：绑定/清空/继承显示正确

## 5. 对接 P1/P2（预留）

- [x] 5.1 与 P1 对齐 embedding 角色字段命名，合入后接入解析器
- [x] 5.2 与 P2 对齐 rerank 角色字段命名，合入后接入解析器
- [x] 5.3 占位角色在状态面板标注「未启用」

## 6. 文档

- [x] 6.1 更新 `超级大脑增强路线.md`：P3 落地与角色说明
- [x] 6.2 README/帮助手册补充「按角色配模型」用法与回退规则
