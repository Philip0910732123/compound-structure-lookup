#!/usr/bin/env python3
"""推送源码到 GitHub + 创建 Release + 上传 exe"""
import subprocess, json, sys, os, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_URL = "https://github.com/Philip0910732123/compound-structure-lookup"
REPO_API = "https://api.github.com/repos/Philip0910732123/compound-structure-lookup"
TOKEN = os.environ.get("GH_TOKEN", "")
EXE_PATH = os.path.join(HERE, "dist", "compound-lookup.exe")

def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd or HERE, capture_output=True, text=True, timeout=120)
    if check and r.returncode != 0:
        print(f"FAIL: {' '.join(cmd)}")
        print(f"STDOUT: {r.stdout}")
        print(f"STDERR: {r.stderr}")
        sys.exit(1)
    return r

# 1. 提取 token（如果环境变量没有）
if not TOKEN:
    inp = "protocol=https\nhost=github.com\n\n"
    r = subprocess.run(["git", "credential", "fill"], input=inp, capture_output=True, text=True, timeout=10)
    for line in r.stdout.strip().split("\n"):
        if line.startswith("password="):
            TOKEN = line.split("=", 1)[1]
            break
if not TOKEN:
    print("ERROR: No token found")
    sys.exit(1)
print(f"Token: {TOKEN[:8]}...{TOKEN[-4:]}")

# 2. Git init + add + commit + push
print("\n=== Git init & push ===")
# 检查是否已有 .git
if not os.path.exists(os.path.join(HERE, ".git")):
    run(["git", "init"])
    run(["git", "branch", "-M", "main"])
else:
    print("Git repo already exists")

# 创建 .gitignore
gitignore = """__pycache__/
*.pyc
build/
dist/
*.spec
build_log.txt
create_repo.py
test_history.py
history/
"""
with open(os.path.join(HERE, ".gitignore"), "w") as f:
    f.write(gitignore)

run(["git", "add", "-A"])
r = run(["git", "status", "--porcelain"])
if r.stdout.strip():
    run(["git", "commit", "-m", "v3.5-exe: RDKit.js + Excel upload + history + auto browser",
         "-m", "Features:",
         "-m", "- RDKit.js client-side structure rendering (WASM, 3-tier fallback)",
         "-m", "- Excel upload with smart column detection",
         "-m", "- History records with timestamp (auto-save to history/)",
         "-m", "- Auto-open browser on exe launch",
         "-m", "- Structure hover tooltip + click lightbox + mouse wheel zoom",
         "-m", "- 6-level data source fallback (CACTUS/PubChem/NIST/Wikidata/CompTox)",
         "-m", "- No API key required"])
    print("Committed successfully")
else:
    print("Nothing to commit")

# 添加 remote 并 push
run(["git", "remote", "remove", "origin"], check=False)
run(["git", "remote", "add", "origin", REPO_URL + ".git"])
run(["git", "push", "-u", "origin", "main"])
print("Pushed to GitHub")

# 3. 创建 Release
print("\n=== Creating GitHub Release ===")
release_data = json.dumps({
    "tag_name": "v3.5",
    "target_commitish": "main",
    "name": "v3.5 — RDKit.js 结构渲染 + Excel 上传 + 历史记录",
    "body": """## 新增功能

### RDKit.js 客户端结构式渲染
- 基于 WebAssembly，浏览器端实时渲染 SMILES → SVG，零网络依赖
- 三级结构式图片兜底：PubChem PNG → RDKit.js SVG → CACTUS PNG
- 矢量图可无损缩放，适用于任何分辨率

### 结构式交互优化
- 悬停浮动大图跟随鼠标移动（最大 300×300px，自动避屏幕边缘）
- 点击全屏灯箱 + 鼠标滚轮缩放（30%~500%）
- 右上角实时显示缩放百分比

### Excel 上传
- 智能检测化合物列（表头关键词匹配 + 非数字列回退）
- 无需固定格式，无需模板，数据放任意列均可

### 历史记录
- 查询结果自动保存到 exe 同目录 `history/` 文件夹
- 文件命名：`history_YYYYMMDD_HHMMSS.json`（时间戳）
- 支持查看详情、下载 CSV/JSON、删除

### 自动打开浏览器
- 双击 exe 后 1.5 秒自动打开 `http://127.0.0.1:5173`

## 数据源（六级兜底）

| 级别 | 数据源 | 获取字段 |
|------|--------|---------|
| Level 1 | NCI CACTUS | SMILES, CAS, IUPAC, 分子式, 分子量, InChIKey |
| Level 2 | PubChem PUG REST + PUG-View | 全字段 + CID（CAS 四重提取） |
| Level 2b | NIST Chemistry WebBook | CAS |
| Level 2c | Wikidata SPARQL | CAS（批量查询） |
| Level 2d | EPA CompTox Dashboard | CAS |

## 使用方式

1. 下载 `compound-lookup.exe`
2. 双击运行 → 浏览器自动打开
3. 输入化合物列表或上传 Excel
4. 点击"开始查询" → 实时查看结果
5. 下载 CSV/JSON 或查看历史记录

## 技术栈

- Python 3.12 + Flask
- RDKit.js (WebAssembly) — 客户端化学结构渲染
- openpyxl — Excel 解析
- PyInstaller — exe 打包""",
    "draft": False,
    "prerelease": False
}).encode("utf-8")

req = urllib.request.Request(
    f"{REPO_API}/releases",
    data=release_data,
    headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    },
    method="POST"
)

release_id = None
upload_url = None
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    release_id = result["id"]
    upload_url = result["upload_url"].split("{")[0]
    html_url = result["html_url"]
    print(f"Release created: {html_url}")
    print(f"Release ID: {release_id}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    print(f"HTTP Error {e.code}: {body}")
    sys.exit(1)

# 4. 上传 exe
print("\n=== Uploading exe ===")
if not os.path.exists(EXE_PATH):
    print(f"ERROR: exe not found at {EXE_PATH}")
    sys.exit(1)

exe_size = os.path.getsize(EXE_PATH)
print(f"exe size: {exe_size / 1024 / 1024:.1f} MB")

with open(EXE_PATH, "rb") as f:
    exe_data = f.read()

upload_req = urllib.request.Request(
    f"{upload_url}?name=compound-lookup.exe&label=compound-lookup.exe",
    data=exe_data,
    headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/octet-stream"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(upload_req, timeout=300) as resp:
        upload_result = json.loads(resp.read())
    print(f"exe uploaded: {upload_result['browser_download_url']}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    print(f"Upload failed: HTTP {e.code}: {body}")
    sys.exit(1)

# 5. 更新 repo topics
print("\n=== Updating repo topics ===")
topics_data = json.dumps({
    "names": ["chemistry", "compound", "smiles", "cas", "rdkit", "pubchem", "flask", "windows-exe", "structure-rendering", "batch-query"]
}).encode("utf-8")
topics_req = urllib.request.Request(
    f"{REPO_API}/topics",
    data=topics_data,
    headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.mercy-preview+json",
        "Content-Type": "application/json"
    },
    method="PUT"
)
try:
    with urllib.request.urlopen(topics_req, timeout=15) as resp:
        print("Topics updated")
except Exception as e:
    print(f"Topics update failed: {e}")

# 6. 更新 repo description
desc_data = json.dumps({
    "description": "化合物结构信息批量查询工具 | 双击exe即可使用 | 六级数据源兜底 | RDKit.js客户端结构渲染 | Excel上传 | 历史记录 | 无需API Key"
}).encode("utf-8")
desc_req = urllib.request.Request(
    f"{REPO_API}",
    data=desc_data,
    headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    },
    method="PATCH"
)
try:
    with urllib.request.urlopen(desc_req, timeout=15) as resp:
        print("Description updated")
except Exception as e:
    print(f"Description update failed: {e}")

print("\n=== ALL DONE ===")
print(f"Repo: {REPO_URL}")
print(f"Release: {html_url}")
print(f"Download: https://github.com/Philip0910732123/compound-structure-lookup/releases/download/v3.5/compound-lookup.exe")
