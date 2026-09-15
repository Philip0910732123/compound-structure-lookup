# 化合物结构信息查询工具 v3.1 使用说明

## 数据获取优先级

| 级别 | 数据源 | 查询方式 | 消耗MCP积分 | 状态 |
|------|--------|---------|------------|------|
| Level 0 | RDKit 本地计算 | SMILES → InChIKey + InChI | 否 | ✅ 新增 |
| Level 1 | NCI CACTUS | SMILES/name → CAS/IUPAC/Formula/MW | 否 | ✅ 可用 |
| Level 2 | PubChem PUG REST | InChIKey优先 → CID → properties/synonyms/xrefs | 否 | ✅ 增强 |
| Level 2 | PubChem PUG-View | CID → EPA DSSTox/FDA SRS CAS | 否 | ✅ 可用 |
| Level 2 | PubChem DepositorRegistryID | CID → depositor CAS | 否 | ✅ 可用 |
| Level 2b | NIST Chemistry WebBook | InChIKey → CAS 精确匹配 | 否 | ✅ 新增 |
| Level 2c | Wikidata SPARQL | InChIKey → CAS 批量查询 | 否 | ✅ 可用 |
| Level 2d | EPA CompTox Dashboard | InChIKey → CAS | 否 | ✅ 可用 |
| ~~Level 3~~ | ~~智慧芽 MCP~~ | ~~已移除（不返回CAS）~~ | — | ❌ 移除 |
| ~~ChemIDplus~~ | ~~NLM/NIH~~ | ~~已退役(2022.12)~~ | — | ❌ 移除 |

## CAS 校验码验证

所有提取的 CAS 号均通过校验码验证：
- CAS 格式：dddddd-dd-d（2-7位数字-2位数字-1位校验码）
- 校验算法：从右到左，各位数字乘以位置索引(1,2,3...)，求和 mod 10 = 校验码
- 减少正则误匹配（如专利号、日期、其他注册号被误识别为 CAS）

## 状态标签

| 状态 | 说明 |
|------|------|
| 完整 | SMILES、CAS、IUPAC 三项均获取成功 |
| 部分 | 至少 1 项成功，CAS已获取 |
| 部分(CAS未注册) | SMILES/IUPAC已获取，但所有数据源均未找到CAS |
| 失败 | 所有数据源均未返回有效数据 |

## v3.1 变更记录

| 改进 | 说明 |
|------|------|
| M. CACTUS InChIKey 查询路径 | 新增 InChIKey 作为 CACTUS 查询标识符 |
| N. PubChem 503 重试 | 指数退避重试 |
| O. PubChem annotations 端点 | 新增从 annotations 提取 CAS 号 |
| P. 全局 CAS 校验码验证 | 所有 CAS 号均通过校验码验证 |
| Q. API 可用性测试文档 | 记录 20+ 数据源的实际可用性状态 |

## v3.2 工程优化（基于 skill-auditor v3.4 审查）

| 改进 | 说明 |
|------|------|
| R. 强制执行层 | SKILL.md 新增门禁+暂停规则 |
| S. 即时落盘 | 每条查询完成即写入 results.ndjson |
| T. 边路径定义 | SKILL.md 新增 IF-THEN 异常处理表 |
| U. 分批处理策略 | >10 个化合物时支持分批+断点恢复 |
| V. selftest 脚本 | 新增 scripts/selftest.py 自检 |
| W. 参数纠正表 | SKILL.md 新增常见错误输入对照 |
| X. measurable_outcome | frontmatter 声明可衡量结果 |
| Y. compatibility 声明 | frontmatter 声明运行环境依赖 |

## 依赖

- requests
- pandas
- rdkit（Level 0 必需，未安装时自动跳过）
