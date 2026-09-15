---
name: compound-structure-lookup
description: 化合物结构信息批量查询工具。输入中英文名称或 SMILES，获取 SMILES、CAS号、IUPAC名称、分子式、分子量、InChIKey、结构图片URL。支持Excel上传、进度回调、CSV/JSON导出。多级数据源兜底确保高覆盖率。
measurable_outcome:
  - 输出字段覆盖率 ≥ 90%（SMILES/CAS/IUPAC/分子式/分子量/InChIKey 六项中至少获取五项）
  - CAS 号校验码通过率 100%
  - 批量查询成功率 ≥ 80%
compatibility:
  - 需要网络访问 NCI CACTUS / PubChem / NIST / Wikidata API
  - RDKit 可选（未安装时自动跳过 Level 0）
  - 无 MCP 工具依赖
---

# 化合物结构信息查询工具 v3.3

## 功能说明

批量查询化合物结构信息，支持中文名、英文名、SMILES 输入，输出：
- 英文名称（中文输入时自动翻译）
- SMILES 字符串
- CAS 号
- IUPAC 名称
- 分子式
- 分子量
- InChIKey
- 数据来源标注
- 状态标签（完整 / 部分 / 部分(CAS未注册) / 失败）
- 结构图片 URL（PubChem CID 优先 / CACTUS SMILES 兜底）
- 进度回调（供 AI 平台实时展示）

## v3.1 变更记录（相比 v3.0）

| 改进 | 说明 |
|------|------|
| M. CACTUS InChIKey 查询路径 | 新增 InChIKey 作为 CACTUS 查询标识符（探针验证可用） |
| N. PubChem 503 重试 | 指数退避重试，解决 PubChem 服务器繁忙问题 |
| O. PubChem annotations 端点 | 新增从 annotations 提取 CAS 号 |
| P. 全局 CAS 校验码验证 | 所有 CAS 号均通过校验码验证 |
| Q. API 可用性测试文档 | 记录 20+ 数据源的实际可用性状态 |


## v3.3 变更记录（2026-09-13，同步 exe v3.5.7）

| 改进 | 说明 |
|------|------|
| R. Excel 输入解析 | `parse_excel()` 智能检测化合物名称列，无需固定格式 |
| S. 结构图片 URL | PubChem CID 优先 / CACTUS SMILES 兜底，三级兜底 |
| T. 进度回调机制 | `run(progress_callback=...)` 供 AI 平台实时展示查询进度 |
| U. CSV/JSON 导出 | 无 pandas 依赖，csv 模块轻量导出 |
| V. CAS 预计算 | 富集前预判状态，SSE 推送时状态不为空 |
| W. parse_input | 逗号/换行分隔自动解析 |

### Excel 输入说明

无需固定格式，`parse_excel()` 采用两级智能检测：
1. 表头关键词匹配（优先）：扫描第一行，找"化合物名称/name/compound/SMILES"等关键词所在列
2. 回退策略：找不到表头时，选第一个有 ≥2 个非纯数字值的列
3. 表头跳过：仅当 Step 1 匹配到表头时才跳过第一行，无表头时不跳

### 结构图片三级兜底

| 优先级 | 来源 | 说明 |
|--------|------|------|
| Tier 1 | PubChem PNG | 有 CID 时用官方高清位图 |
| Tier 2 | SmilesDrawer Canvas | 有 SMILES 时纯 JS 渲染，CPK 着色（exe 专属） |
| Tier 3 | CACTUS PNG | 网络兜底 |

### 进度回调接口

```python
def progress_callback(current, total, compound_name, row_dict, phase):
    # phase: 'querying' | 'enriching' | 'done' | 'complete'
    pass
```

AI 平台调用时传入回调函数即可实时获取每条化合物的查询进度和结果。


## 数据获取策略（六级兜底）

### Level 0: RDKit 本地 InChIKey 计算（不消耗任何外部 API）
- 用 RDKit 从 SMILES 本地计算 InChIKey 和 InChI
- 解决 PubChem SMILES 搜索失败时无 InChIKey 的问题
- 确保 100% InChIKey 覆盖率，为下游 InChIKey 查询提供基础

### Level 1: NCI CACTUS（不消耗MCP积分）
- [v3.1新增] 支持 SMILES 和 InChIKey 双路径查询
- SMILES/InChIKey → CAS → IUPAC → 分子式 → 分子量 → InChIKey
- InChIKey 路径在 SMILES 搜索失败时提供额外查询机会

### Level 2: PubChem PUG REST + PUG-View + DepositorRegistryID + annotations
- [v3.1新增] 503 错误指数退避重试
- [v3.1新增] annotations 端点提取 CAS
- 优先用 InChIKey 搜索（比 SMILES 更鲁棒）
- PUG REST: 获取 SMILES、IUPAC、分子式、分子量、InChIKey
- PUG REST xrefs RegistryID + synonyms: 提取 CAS
- PUG-View: 从 EPA DSSTox/FDA SRS/NIST 等数据源完整记录中提取 CAS
- DepositorRegistryID xref: PubChem depositor 提交的注册号
- annotations: 从 PubChem 注释中提取 CAS

### Level 2b: NIST Chemistry WebBook
- 用 InChIKey 查询 NIST 化学手册
- 精确模式提取 CAS

### Level 2c: Wikidata SPARQL 批量查询
- 单次 SPARQL 查询所有缺 CAS 的 InChIKey（wdt:P235 → wdt:P231）
- 在所有单条查询完成后批量执行，3秒完成

### Level 2d: EPA CompTox Dashboard（API 端点可能已迁移，保留兜底）


### 数据流决策树

```
输入化合物
    │
    ├─ 是 SMILES？─是→ RDKit 计算InChIKey ──→ CACTUS(SMILES) ──→ 字段完整？
    │                    │                                       │
    │                    └─ RDKit不可用 → CACTUS(SMILES) ────────┤
    │                                                            │
    └─ 是名称？─是→ 翻译 → CACTUS(名称) ──────────────────────┤
                                                                 │
    字段完整？─是→ 完成 ✓                                        │
         │                                                       │
         └─ 否 → 缺哪些字段？                                     │
              ├─ 缺 SMILES/CAS/分子式 → PubChem(InChIKey) ──→ 补全？─是→ 完成 ✓
              │                                                    │
              │                                                    └─ 否→ 继续↓
              │
              ├─ 仍缺 CAS → NIST(InChIKey) ──→ 找到？─是→ 完成 ✓
              │                                      │
              │                                      └─ 否→ Wikidata SPARQL(批量) ──→ 找到？─是→ 完成 ✓
              │                                                                         │
              │                                                                         └─ 否→ CompTox ──→ 找到？─是→ 完成 ✓
              │                                                                                          │
              │                                                                                          └─ 否→ 状态="部分(CAS未注册)"
              │
              └─ 全部缺失 → 状态="失败"
```


## CAS 校验码验证

所有提取的 CAS 号均通过校验码验证：
- CAS 格式：dddddd-dd-d（2-7位数字-2位数字-1位校验码）
- 校验算法：从右到左，各位数字乘以位置索引(1,2,3...)，求和 mod 10 = 校验码
- 减少正则误匹配（如专利号、其他注册号被误识别为 CAS）

## 状态标签

| 状态 | 说明 |
|------|------|
| 完整 | SMILES、CAS、IUPAC 三项均获取成功 |
| 部分 | 至少 1 项成功，但不完整（CAS已获取） |
| 部分(CAS未注册) | SMILES/IUPAC已获取，但所有数据源均未找到CAS（化合物可能未注册CAS） |
| 失败 | 所有数据源均未返回有效数据 |

## v3.1 API 可用性测试结果（2026-07-25）

| 数据源 | 状态 | 说明 |
|--------|------|------|
| NCI CACTUS (SMILES) | ✅ 可用 | 主力数据源，支持 SMILES 和名称查询 |
| NCI CACTUS (InChIKey) | ✅ 可用 | [v3.1新增] InChIKey 直接查询 CAS |
| PubChem PUG REST | ✅ 可用 | InChIKey/SMILES → CID → properties/synonyms |
| PubChem PUG-View | ✅ 可用 | CID → 完整记录 → CAS 提取 |
| Wikidata SPARQL | ✅ 可用 | InChIKey → CAS 批量查询 |
| RDKit 本地 | ✅ 可用 | SMILES → InChIKey 本地计算 |
| CAS Common Chemistry | ❌ 需 API key | 2026年起需要 X-API-KEY header |
| UniChem (EBI) | ❌ 端点 404 | REST API 已迁移或下线 |
| ChEBI | ❌ 端点 404/500 | REST API 已迁移或下线 |
| EPA CompTox | ❌ 端点 404 | API 端点已迁移 |
| FDA UNII | ❌ DNS 失败 | fdasis.nlm.nih.gov 无法解析 |
| ChemBlink | ❌ 404 | 网站已改版 |
| Wikipedia | ❌ 连接超时 | 从 Python 环境无法访问 |
| ChemicalBook | ❌ web_fetch 失败 | 网络不可达 |
| 智慧芽 MCP | ❌ 不含 CAS | ls_structure_fetch/search 不返回 CAS 字段 |

## When to use

以下场景触发本工具：
- 用户给出化合物名称（中文或英文），需要获取 SMILES/CAS/IUPAC/分子式/分子量/InChIKey
- 用户粘贴 SMILES 列表，需要反向查询 CAS 号和 IUPAC 名称
- 用户上传 Excel 化合物清单，需要批量补全结构信息
- 用户需要化合物结构图片 URL 用于报告或展示
- 与其他 skill 配合时，需要 InChIKey 作为化合物唯一标识

## 使用方式

直接说出化合物名称，例如：
- "查询阿司匹林、布洛芬的结构信息"
- "查询 osimertinib, furmonertinib"
- 粘贴 SMILES 列表

## 输出
- 对话中显示 Markdown 表格
- 生成 compounds_result.csv 和 compounds_result.json


## 强制执行层

以下条件为硬性流程，不满足时**必须暂停**：

1. **输入化合物列表必须非空**：空列表时停止，提示用户输入化合物名称/SMILES
2. **RDKit 不可用时必须提示**：输出 `[RDKit] 未安装，Level 0 不可用（建议 pip install rdkit）`，不静默跳过
3. **输出 CSV/JSON 必须包含所有输入化合物对应行**：每条输入至少有一行输出（即使状态为"失败"）

### 暂停规则

遇到以下情况必须暂停并向用户报告：

- **输入化合物列表为空** → 暂停，提示用户输入
- **RDKit 未安装且输入含 SMILES** → 暂停，提示安装 rdkit（SMILES 输入依赖 RDKit 计算 InChIKey）
- **所有数据源（CACTUS + PubChem + Wikidata + NIST）均不可达** → 暂停，提示网络问题

## 边路径定义

每个关键步骤的异常处理分支：

| 步骤 | 条件 | 处理 | 后果传播 |
|------|------|------|---------|
| Level 0 | RDKit 未安装 | 跳过 Level 0，直接从 Level 1 开始 | 无 InChIKey → NIST/Wikidata/CompTox 三层后续可能失效 |
| Level 0 | SMILES 解析失败 | 跳过该化合物，标记状态="失败" | 该化合物无任何输出 |
| Level 1 | NCI CACTUS 返回 503/超时 | safe_get 指数退避重试 3 次，仍失败则跳过该数据源 | 无 SMILES/CAS/IUPAC → 仅靠 PubChem 补全 |
| Level 2 | PubChem SMILES 搜索无结果 | 改用 RDKit InChIKey 搜索（PubChem InChIKey 路径） | 若 RDKit 也不可用 → 无 CID → 无结构图片 |
| Level 2b-d | NIST/Wikidata/CompTox 查询失败 | 跳过该数据源，继续后续数据源 | CAS 号可能缺失 → 状态降级为"部分(CAS未注册)" |
| 后置 CAS 富集 | 所有数据源均未返回 CAS | 标记状态="部分(CAS未注册)" | 最终输出 CAS 列为空，影响下游 CAS 依赖查询 |
| 输入 | 化合物名为空或纯空白 | 返回 None，跳过 | 不产生任何输出行 |
| 翻译 | MyMemory API 不可用 | 返回原始名称，继续查询 | 中文名可能查询失败（CACTUS 不识别中文） |


### 多层穿透分析（DID-002）

六级数据源看似独立兜底，但存在以下穿透路径：

**穿透路径 1：RDKit 不可用 → InChIKey 缺失 → NIST/Wikidata/CompTox 三层同时失效**
- Level 0（RDKit）不可用 → 无 InChIKey
- Level 1（CACTUS）未返回 InChIKey → 仍无 InChIKey
- Level 2（PubChem）未返回 InChIKey → 仍无 InChIKey
- Level 2b（NIST）依赖 InChIKey 查询 → 跳过
- Level 2c（Wikidata）依赖 InChIKey 查询 → 跳过
- Level 2d（CompTox）依赖 InChIKey 查询 → 跳过
- **后果**：CAS 号只能靠 CACTUS + PubChem 两层，覆盖率下降

**穿透路径 2：网络完全不可达 → 所有在线数据源同时失效**
- CACTUS/PubChem/NIST/Wikidata/CompTox 全部依赖网络
- RDKit 本地可计算 InChIKey 但无法获取 CAS/IUPAC/分子式
- **后果**：只能输出 SMILES + InChIKey（来自 RDKit），状态标记"部分"

**缓解措施**：
1. 启动时探测网络连通性（CACTUS ping），网络不可达时提前暂停
2. RDKit 可用时优先计算 InChIKey，为后续在线查询提供基础
3. Wikidata SPARQL 批量查询减少网络请求次数

### 防御层覆盖矩阵

| 字段 \ 数据源 | RDKit L0 | CACTUS L1 | PubChem L2 | NIST L2b | Wikidata L2c | CompTox L2d |
|--------------|----------|-----------|------------|----------|-------------|-------------|
| SMILES | — | ✅ 主 | ✅ 补 | — | — | — |
| CAS号 | — | ✅ 主 | ✅ 补(4重) | ✅ 补 | ✅ 批量补 | ✅ 补 |
| IUPAC | — | ✅ 主 | ✅ 补 | — | — | — |
| 分子式 | — | ✅ 主 | ✅ 补 | — | — | — |
| 分子量 | — | ✅ 主 | ✅ 补 | — | — | — |
| InChIKey | ✅ 主 | ✅ 补 | ✅ 补 | — | — | — |
| CID | — | — | ✅ 唯一 | — | — | — |
| 结构图片 | — | ✅ 兜底 | ✅ 主 | — | — | — |


## 分批处理策略

批量查询（>10 个化合物）时采用分批处理：

1. **批次大小**：每批 20 个化合物
2. **断点恢复**：batch_state.json 记录当前批次/进度，中断后从断点继续
3. **即时落盘**：每条化合物查询完成后 append 到 results.ndjson
4. **最终合并**：所有批次完成后 merge 为 compounds_result.csv/json

### 参数纠正表

| 常见错误输入 | 正确方式 | 说明 |
|---|---|---|
| 传入中文名未翻译 | 直接传入 | 脚本 translate_name() 自动翻译 |
| SMILES 含空格 | 去除空格后传入 | is_smiles() 可能误判 |
| CAS 号含前导零 | 保持标准格式 dddddd-dd-d | validate_cas() 校验 |
| 逗号分隔的化合物列表 | 逗号或换行分隔均可 | 脚本用 re.split(r'[,\n]+') 分割 |
| 混合中英文+SMILES | 直接传入 | 脚本自动检测 SMILES 并处理 |


### Phase 契约（前置/后置条件）

| Phase | 前置条件 | 后置条件 |
|-------|---------|----------|
| Phase 1: 输入解析 | compounds 列表非空 AND OUT_DIR 可写 | parse_input 返回 ≥1 个有效化合物 |
| Phase 2: 逐条查询 | Phase 1 后置满足 AND (RDKit 可用 OR 网络可达) | len(results) == len(compounds) AND results.ndjson 行数 == len(results) |
| Phase 3: CAS 富集 | Phase 2 后置满足 AND 至少 1 条 CAS 缺失 | 所有 CAS 缺失项已尝试 NIST + Wikidata + CompTox |
| Phase 4: 导出 | Phase 3 后置满足 AND len(results) > 0 | compounds_result.csv 行数 == len(results) + 1（表头） |

**契约违反处理**：任一前置条件不满足时暂停并报错；后置条件不满足时记录 WARN 但继续执行。

### 规模化临界点

| 规模 | 临界点 | 风险 | 缓解措施 |
|------|--------|------|----------|
| Wikidata SPARQL | VALUES 子句 > 50 个 InChIKey | 查询超长被拒绝 | 分批查询，每批 50 个 |
| PubChem PUG REST | > 5 请求/秒 | 503 Too Many Requests | 指数退避重试（已有） |
| 批量查询 | > 100 个化合物 | 上下文堆积、单次运行时间过长 | 分批 20 个/批，NDJSON 即时落盘 |

## 融合钩子

本工具可与其他 skill 衔接，形成工作流：

| 衔接 skill | 输入 → 输出 | 典型工作流 |
|------------|------------|-----------|
| cheminformatics-toolkit | 本工具输出 SMILES → 计算类药性/相似性 | 查询化合物 → 筛选类药性 |
| bio-sequence-toolkit | 本工具输出 InChIKey → 交叉验证 | 化合物 → 序列关联分析 |
| biomarker-investigation | 本工具输出 CAS 号 → 文献检索 | 化合物 → 标志物文献 |
| compound-structure-lookup (exe) | Excel 输入 → 本 skill 批量处理 | exe 查询 → skill 二创 |

**调用方式**：AI 平台中先调用本 skill 获取化合物结构信息，将输出（SMILES/CAS/InChIKey）作为下游 skill 的输入参数。
