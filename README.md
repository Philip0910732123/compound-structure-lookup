# Compound Structure Lookup

🔬 化合物结构信息批量查询工具 — 两种使用方式，按需选择。

## 两种使用方式

| 方式 | 适合谁 | 说明 |
|------|--------|------|
| **📦 桌面 exe** | 所有用户 | 双击即用，无需 Python，无需 LLM，浏览器内操作 |
| **🤖 AI Skill** | AI 平台开发者 | 导入 AI Coding 平台（如 Eureka/Claude/Cursor），批量调用，可嵌入工作流，支持二创 |

### 桌面 exe 版本（免 LLM）

- 双击 `compound-lookup.exe` → 浏览器自动打开 → 粘贴化合物列表 → 查询 → 下载 CSV/JSON
- 无需安装任何环境，无需 API Key
- 下载地址：[最新 Release](https://github.com/Philip0910732123/compound-structure-lookup/releases)

### AI Skill 版本（需 LLM）

- 将 `skill/` 目录导入 AI Coding 平台即可作为 Skill 调用
- LLM 负责解析用户意图、调用脚本、展示结果；Python 脚本负责数据查询
- 支持批量查询、进度回调、NDJSON 即时落盘、断点恢复
- 消耗大模型 token，由用户按需选择
- 其他开发者可 fork 做二创，嵌入自己的工作流

---

## 功能

- **批量查询**：支持中英文名称 / SMILES / Excel 上传
- **多级数据源兜底**：CACTUS → PubChem → NIST → Wikidata → CompTox
- **SmilesDrawer 客户端结构式渲染**：纯 JavaScript，浏览器端实时渲染 SMILES → Canvas，CPK 着色，零网络依赖
- **三级结构式图片兜底**：PubChem PNG → SmilesDrawer Canvas → CACTUS PNG
- **Kekulé 双键渲染**：苯环显示为三条交替双键（非圆圈），双键间距加宽，清晰区分环己烷
- **结构式交互**：悬停浮动大图跟随鼠标 + 点击全屏灯箱 + 鼠标滚轮缩放
- **Excel 上传**：智能检测化合物列，无需固定格式，无需模板
- **历史记录**：查询结果自动保存到 exe 同目录 `history/` 文件夹，带时间戳命名
- **自动打开浏览器**：双击 exe 后 1.5 秒自动打开操作页面
- **无需 API Key**：所有数据源均为公开 API

## 输出字段

| 字段 | 说明 |
|------|------|
| SMILES | 规范 SMILES 字符串 |
| CAS 号 | 通过校验码验证的 CAS 号 |
| IUPAC 名称 | 系统命名 |
| 分子式 | 如 C9H8O4 |
| 分子量 | 如 180.16 |
| InChIKey | 国际化学标识符 |
| 结构式图片 | PubChem PNG / SmilesDrawer Canvas / CACTUS PNG |
| 数据来源 | 标注每个字段来自哪个数据源 |
| 状态 | 完整 / 部分 / 部分(CAS未注册) / 失败 |

## 桌面 exe 使用方式

1. 下载 [最新 Release](https://github.com/Philip0910732123/compound-structure-lookup/releases) 中的 `compound-lookup.exe`
2. 双击运行 → 浏览器自动打开 `http://127.0.0.1:5173`
3. 输入化合物列表（每行一个名称或 SMILES，也可逗号分隔）
4. 或点击"📁 上传 Excel"导入化合物列表
5. 点击"开始查询" → 实时查看进度和逐条结果
6. 下载 CSV / JSON，或查看历史记录

## AI Skill 使用方式

### 安装

将 `skill/` 目录导入 AI Coding 平台（如 Eureka）：

```
skill/
├── SKILL.md                    # Skill 文档（skill-auditor v3.4 认证）
├── skill.manifest.json          # 依赖声明
├── references/
│   └── usage.md                 # 使用说明
└── scripts/
    ├── compound_lookup.py       # 查询引擎（837行）
    ├── selftest.py              # 5 项自检
    └── main.py                  # 入口桩
```

### 调用示例

在 AI 平台中直接说出需求：
- "查询阿司匹林、布洛芬的结构信息"
- "查询 osimertinib, furmonertinib"
- 粘贴 SMILES 列表

### Skill 依赖

```
rdkit      # Level 0 本地 InChIKey 计算（可选，未安装时自动跳过）
requests   # 网络请求
openpyxl   # Excel 解析
```

### Skill 与 exe 的能力对比

| 能力 | 桌面 exe | AI Skill |
|------|---------|---------|
| 批量查询 | ✅ | ✅ |
| Excel 上传 | ✅ | ✅ |
| 结构式渲染 | ✅ SmilesDrawer | ❌ 返回结构图片 URL |
| 历史记录 | ✅ | ❌ 由 AI 平台管理 |
| 断点恢复 | ❌ | ✅ NDJSON + batch_state |
| 进度回调 | ❌ | ✅ progress_callback |
| RDKit Level 0 | ❌（exe 不含 RDKit） | ✅（skill 环境有 RDKit） |
| 二创定制 | 改源码 | ✅ fork skill |
| token 消耗 | 免费 | 消耗大模型 token |

## 数据源说明

| 级别 | 数据源 | 获取字段 | 说明 |
|------|--------|---------|------|
| Level 0 | RDKit 本地 | InChIKey | 不消耗 API（仅 Skill 版本可用） |
| Level 1 | NCI CACTUS | SMILES, CAS, IUPAC, 分子式, 分子量, InChIKey | 主力数据源 |
| Level 2 | PubChem PUG REST + PUG-View | 全字段 + CID | CAS 四重提取策略 |
| Level 2b | NIST Chemistry WebBook | CAS | 精确模式 |
| Level 2c | Wikidata SPARQL | CAS | 批量查询 |
| Level 2d | EPA CompTox Dashboard | CAS | 兜底 |

## 结构式渲染

**渲染引擎**：SmilesDrawer 2.4.1（纯 JavaScript，~100KB）

**CPK 着色方案**：

| 元素 | 颜色 | 色值 |
|------|------|------|
| 碳 C | 深灰 | #222 |
| 氧 O | 红色 | #e00e0e |
| 氮 N | 蓝色 | #3050f8 |
| 硫 S | 黄色 | #e6c200 |
| 氯 Cl | 绿色 | #1ff01f |
| 磷 P | 橙色 | #ff8000 |
| 溴 Br | 深红 | #a62929 |
| 碘 I | 紫色 | #9c09d7 |

**三级图片兜底**：

1. **PubChem PNG** — 有 CID 时使用官方高清位图
2. **SmilesDrawer Canvas** — 有 SMILES 时浏览器端渲染，CPK 着色，Kekulé 双键，白底
3. **CACTUS PNG** — 最终兜底

**Kekulé 双键状态机**：在 SMILES 传入 SmilesDrawer 前做逐字符状态机转换，将芳香原子（小写 c/n/o/s/b/p）的隐式键替换为交替 `=` 双键并大写，确保苯环显示为三条双键而非圆圈。

## 仓库结构

```
compound-structure-lookup/
├── app.py                      # exe 后端（Flask + 内嵌 HTML）
├── compound_engine.py          # exe 查询引擎
├── build_exe.py                # PyInstaller 构建脚本
├── requirements.txt            # exe 依赖
├── README.md
├── LICENSE
└── skill/                      # AI Skill 版本
    ├── SKILL.md                # Skill 文档（skill-auditor v3.4 认证）
    ├── skill.manifest.json
    ├── references/
    │   └── usage.md
    └── scripts/
        ├── compound_lookup.py  # 查询引擎
        ├── selftest.py         # 自检脚本
        └── main.py
```

## 技术栈

- Python 3.12 + Flask
- SmilesDrawer 2.4.1 — 客户端化学结构渲染
- openpyxl — Excel 解析
- PyInstaller — exe 打包

## 从源码运行（exe 版本）

```bash
pip install flask requests openpyxl
python app.py
```

## 版本历史

### v3.5.7 (2026-09-13)
- 加宽双键间距（bondSpacing 1.2→6px），苯环双键清晰区分环己烷
- 加粗键线（bondThickness 1.5→1.8px）

### v3.5.6 (2026-09-13)
- 新增 `kekulizeSmiles()` 逐字符状态机，将芳香 SMILES 转为 Kekulé 结构
- 苯环显示为三条交替双键，不再显示圆圈
- 9 项 Python 单元测试全部通过（苯、吡啶、萘、噻吩、阿司匹林等）

### v3.5.5 (2026-09-13)
- 白色背景：SmilesDrawer 配置 + Canvas CSS + dataURL 导出三重白底保障
- 苯环改为 Kekulé 双键（`compactDrawing: false`）

### v3.5.4 (2026-09-13)
- 用 SmilesDrawer 2.4.1 替换 RDKit.js（纯 JS，~100KB，无 WASM 依赖）
- CPK 着色方案默认启用
- 三级图片兜底：PubChem PNG → SmilesDrawer Canvas → CACTUS PNG

### v3.5.3 (2026-09-13)
- 修复 RDKit.js 竞态条件（脚本异步加载 Promise 追踪）
- 统一渲染管线：所有化合物先网络图片占位再尝试 JS 渲染替换
- 状态字段预计算：修复查询页状态显示红杠问题

### v3.5.2 (2026-09-13)
- 修复 RDKit.js CDN 版本号错误（2024.3.4-1.0.0 → 2025.3.4-1.0.0）
- 双源容错：jsdelivr 主源 + unpkg 备源

### v3.5.1 (2026-09-13)
- 修复 RDKit.js WASM 无法加载：添加 locateFile 配置
- 修复 CACTUS 兜底图无交互事件
- 修复查询页状态显示红杠：query_compound() 返回前预计算状态

### v3.5-exe (2026-09-13)
- 结构式渲染（初始 RDKit.js）
- 结构式悬停浮动大图 + 点击全屏灯箱 + 鼠标滚轮缩放
- Excel 上传智能列检测
- 历史记录功能（自动保存 + 查看 + 下载 + 删除）
- 自动打开浏览器

### v3.0-exe
- 首个 exe 版本
- CSV/JSON 导出

## License

MIT
