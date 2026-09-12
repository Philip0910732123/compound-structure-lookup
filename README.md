# Compound Structure Lookup

🔬 化合物结构信息批量查询工具 — 双击 exe 即可使用，无需安装 Python 环境。

## 功能

- **批量查询**：支持中英文名称 / SMILES / Excel 上传
- **六级数据源兜底**：CACTUS → PubChem → NIST → Wikidata → CompTox
- **RDKit.js 客户端结构式渲染**：基于 WebAssembly，浏览器端实时渲染 SMILES → SVG，零网络依赖
- **三级结构式图片兜底**：PubChem PNG → RDKit.js SVG → CACTUS PNG
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
| 结构式图片 | PubChem PNG / RDKit.js SVG / CACTUS PNG |
| 数据来源 | 标注每个字段来自哪个数据源 |
| 状态 | 完整 / 部分 / 部分(CAS未注册) / 失败 |

## 使用方式

1. 下载 [最新 Release](https://github.com/Philip0910732123/compound-structure-lookup/releases) 中的 `compound-lookup.exe`
2. 双击运行 → 浏览器自动打开 `http://127.0.0.1:5173`
3. 输入化合物列表（每行一个名称或 SMILES，也可逗号分隔）
4. 或点击"📁 上传 Excel"导入化合物列表
5. 点击"开始查询" → 实时查看进度和逐条结果
6. 下载 CSV / JSON，或查看历史记录

## 数据源说明

| 级别 | 数据源 | 获取字段 | 说明 |
|------|--------|---------|------|
| Level 1 | NCI CACTUS | SMILES, CAS, IUPAC, 分子式, 分子量, InChIKey | 主力数据源 |
| Level 2 | PubChem PUG REST + PUG-View | 全字段 + CID | CAS 四重提取策略 |
| Level 2b | NIST Chemistry WebBook | CAS | 精确模式 |
| Level 2c | Wikidata SPARQL | CAS | 批量查询 |
| Level 2d | EPA CompTox Dashboard | CAS | 兜底 |

## 结构式渲染优先级

1. **PubChem PNG** — 有 CID 时使用官方高清位图
2. **RDKit.js SVG** — 有 SMILES 时浏览器端 WASM 渲染，矢量图，可无损缩放
3. **CACTUS PNG** — 最终兜底

## 技术栈

- Python 3.12 + Flask
- RDKit.js (WebAssembly) — 客户端化学结构渲染
- openpyxl — Excel 解析
- PyInstaller — exe 打包

## 从源码运行

```bash
pip install flask requests openpyxl
python app.py
```

## 版本历史

### v3.5-exe (2026-09-13)
- 新增 RDKit.js 客户端结构式渲染（三级图片兜底）
- 结构式悬停浮动大图 + 点击全屏灯箱 + 鼠标滚轮缩放
- Excel 上传智能列检测
- 历史记录功能（自动保存 + 查看 + 下载 + 删除）
- 自动打开浏览器

### v3.0-exe
- 首个 exe 版本
- 六级数据源兜底
- CSV/JSON 导出

## License

MIT
