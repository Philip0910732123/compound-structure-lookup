#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
化合物结构信息查询工具 — Web UI 入口
双击 exe → 自动打开浏览器 → 粘贴化合物列表 → 实时查询 → 下载 CSV/JSON

依赖: Flask + requests + compound_engine.py
打包: PyInstaller --onefile
"""

import sys
import os
import json
import time
import threading
import webbrowser
import queue
import glob
import re

from flask import Flask, request, jsonify, Response, send_file
from compound_engine import run, parse_input, parse_excel, export_csv, export_json, COLUMNS

app = Flask(__name__)

# ── 全局状态 ──
_results_store = {}      # task_id → results list
_cancel_flags = {}       # task_id → bool


# ─────────────────────────────────────────────
# 历史记录 — 存储在 exe 同目录下的 history/ 文件夹
# ─────────────────────────────────────────────

def get_base_dir():
    """获取 exe 所在目录（打包后）或脚本所在目录（开发时）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_history_dir():
    """历史记录目录路径"""
    d = os.path.join(get_base_dir(), "history")
    if not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
    return d


def save_history(task_id, compounds_input, results):
    """查询完成后自动保存历史记录到 JSON 文件"""
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"history_{ts}.json"
        filepath = os.path.join(get_history_dir(), filename)

        # 统计摘要
        total = len(results)
        complete = sum(1 for r in results if r.get("状态") == "完整")
        partial = sum(1 for r in results if r.get("状态") == "部分")
        partial_nocas = sum(1 for r in results if r.get("状态") == "部分(CAS未注册)")
        fail = sum(1 for r in results if r.get("状态") == "失败")

        record = {
            "filename": filename,
            "timestamp": ts,
            "timestamp_display": time.strftime("%Y-%m-%d %H:%M:%S"),
            "task_id": task_id,
            "compounds_input": compounds_input[:2000],  # 截断防止过大
            "compound_count": total,
            "summary": {
                "total": total,
                "complete": complete,
                "partial": partial,
                "partial_nocas": partial_nocas,
                "fail": fail,
            },
            "results": results,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        return filename
    except Exception as e:
        print(f"[save_history] 保存失败: {e}", file=sys.stderr)
        return None


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/api/query", methods=["POST"])
def api_query():
    """启动查询，返回 SSE 流（实时进度 + 逐条结果）"""
    data = request.get_json(force=True)
    compounds_text = data.get("compounds", "").strip()
    if not compounds_text:
        return jsonify({"error": "请输入化合物列表"}), 400

    compounds = parse_input(compounds_text)
    if not compounds:
        return jsonify({"error": "未能解析出有效化合物名称"}), 400

    if len(compounds) > 500:
        return jsonify({"error": f"单次最多 500 条，当前 {len(compounds)} 条"}), 400

    task_id = f"task_{int(time.time() * 1000)}"

    def generate():
        progress_q = queue.Queue()

        def progress_cb(current, total, name, row, phase):
            progress_q.put({
                "current": current,
                "total": total,
                "name": name,
                "row": row,
                "phase": phase,
            })

        # 在后台线程中运行查询
        def worker():
            try:
                results = run(compounds, progress_callback=progress_cb)
                _results_store[task_id] = results
                # 自动保存历史记录
                save_history(task_id, compounds_text, results)
            except Exception as e:
                progress_q.put({"error": str(e), "phase": "error"})
                return
            # 发送结束信号
            progress_q.put(None)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        # 从队列读取进度，通过 SSE 推送
        while True:
            try:
                msg = progress_q.get(timeout=120)
            except queue.Empty:
                yield f"event: error\ndata: {json.dumps({'error': '查询超时'})}\n\n"
                break

            if msg is None:
                yield f"event: done\ndata: {json.dumps({'task_id': task_id})}\n\n"
                break

            if msg.get("phase") == "error":
                yield f"event: error\ndata: {json.dumps(msg)}\n\n"
                break

            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no",
                             "Connection": "keep-alive"})


@app.route("/api/results/<task_id>", methods=["GET"])
def api_results(task_id):
    """获取完整结果（JSON）"""
    results = _results_store.get(task_id)
    if results is None:
        return jsonify({"error": "结果不存在或已过期"}), 404
    return jsonify({"results": results, "columns": COLUMNS})


@app.route("/api/download/<task_id>/<fmt>", methods=["GET"])
def api_download(task_id, fmt):
    """下载 CSV 或 JSON 文件"""
    results = _results_store.get(task_id)
    if results is None:
        return jsonify({"error": "结果不存在或已过期"}), 404

    tmp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
    if fmt == "csv":
        filepath = os.path.join(tmp_dir, f"compounds_result_{task_id}.csv")
        export_csv(results, filepath)
        return send_file(filepath, as_attachment=True,
                         download_name="compounds_result.csv",
                         mimetype="text/csv")
    elif fmt == "json":
        filepath = os.path.join(tmp_dir, f"compounds_result_{task_id}.json")
        export_json(results, filepath)
        return send_file(filepath, as_attachment=True,
                         download_name="compounds_result.json",
                         mimetype="application/json")
    else:
        return jsonify({"error": "不支持的格式"}), 400


@app.route("/api/history", methods=["GET"])
def api_history_list():
    """列出所有历史记录（按时间倒序，仅返回摘要）"""
    history_dir = get_history_dir()
    files = sorted(glob.glob(os.path.join(history_dir, "history_*.json")), reverse=True)
    records = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append({
                "filename": data.get("filename", os.path.basename(fp)),
                "timestamp": data.get("timestamp", ""),
                "timestamp_display": data.get("timestamp_display", ""),
                "compound_count": data.get("compound_count", 0),
                "summary": data.get("summary", {}),
                "compounds_preview": data.get("compounds_input", "")[:200],
            })
        except Exception:
            continue
    return jsonify({"history": records, "total": len(records)})


@app.route("/api/history/<filename>", methods=["GET"])
def api_history_detail(filename):
    """获取某条历史记录的完整结果"""
    # 安全检查：只允许 history_*.json 格式的文件名
    if not re.match(r'^history_\d{8}_\d{6}\.json$', filename):
        return jsonify({"error": "无效的文件名"}), 400
    filepath = os.path.join(get_history_dir(), filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "历史记录不存在"}), 404
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({
            "results": data.get("results", []),
            "columns": COLUMNS,
            "meta": {
                "filename": data.get("filename", ""),
                "timestamp_display": data.get("timestamp_display", ""),
                "compound_count": data.get("compound_count", 0),
                "summary": data.get("summary", {}),
                "compounds_input": data.get("compounds_input", ""),
            }
        })
    except Exception as e:
        return jsonify({"error": f"读取失败: {str(e)}"}), 500


@app.route("/api/history/<filename>/download/<fmt>", methods=["GET"])
def api_history_download(filename, fmt):
    """下载某条历史记录的 CSV 或 JSON 文件"""
    if not re.match(r'^history_\d{8}_\d{6}\.json$', filename):
        return jsonify({"error": "无效的文件名"}), 400
    filepath = os.path.join(get_history_dir(), filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "历史记录不存在"}), 404
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = data.get("results", [])
    except Exception as e:
        return jsonify({"error": f"读取失败: {str(e)}"}), 500

    tmp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
    base_name = filename.replace(".json", "")
    if fmt == "csv":
        out_path = os.path.join(tmp_dir, f"{base_name}.csv")
        export_csv(results, out_path)
        return send_file(out_path, as_attachment=True,
                         download_name=f"{base_name}.csv", mimetype="text/csv")
    elif fmt == "json":
        out_path = os.path.join(tmp_dir, f"{base_name}_export.json")
        export_json(results, out_path)
        return send_file(out_path, as_attachment=True,
                         download_name=f"{base_name}_export.json", mimetype="application/json")
    else:
        return jsonify({"error": "不支持的格式"}), 400


@app.route("/api/history/<filename>", methods=["DELETE"])
def api_history_delete(filename):
    """删除某条历史记录"""
    if not re.match(r'^history_\d{8}_\d{6}\.json$', filename):
        return jsonify({"error": "无效的文件名"}), 400
    filepath = os.path.join(get_history_dir(), filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "历史记录不存在"}), 404
    try:
        os.remove(filepath)
        return jsonify({"ok": True, "message": f"已删除 {filename}"})
    except Exception as e:
        return jsonify({"error": f"删除失败: {str(e)}"}), 500



@app.route("/api/upload", methods=["POST"])
def api_upload():
    """上传 Excel 文件，解析化合物列表"""
    if "file" not in request.files:
        return jsonify({"error": "请选择文件"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "请选择文件"}), 400
    if not file.filename.endswith((".xlsx", ".xls")):
        return jsonify({"error": "请上传 Excel 文件 (.xlsx)"}), 400

    tmp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
    tmp_path = os.path.join(tmp_dir, f"upload_{int(time.time())}.xlsx")
    file.save(tmp_path)

    try:
        compounds = parse_excel(tmp_path)
        if not compounds:
            return jsonify({"error": "未在 Excel 中找到有效数据"}), 400
        return jsonify({"compounds": compounds, "text": "\n".join(compounds)})
    except Exception as e:
        return jsonify({"error": f"解析失败: {str(e)}"}), 500
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ─────────────────────────────────────────────
# 内嵌 HTML 前端页面
# ─────────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>化合物结构信息查询工具</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, "Microsoft YaHei", "Segoe UI", sans-serif;
  background: #f0f2f5; color: #333; min-height: 100vh; padding: 20px;
}
.container { max-width: 1200px; margin: 0 auto; }
.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff; padding: 24px 32px; border-radius: 12px;
  margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.header h1 { font-size: 22px; margin-bottom: 6px; }
.header p { font-size: 13px; opacity: 0.9; }
.card {
  background: #fff; border-radius: 12px; padding: 24px;
  margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.card-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #1a1a2e; }
textarea {
  width: 100%; min-height: 120px; padding: 12px; border: 2px solid #e0e0e0;
  border-radius: 8px; font-size: 14px; font-family: "Consolas", monospace;
  resize: vertical; transition: border-color 0.2s;
}
textarea:focus { outline: none; border-color: #667eea; }
.btn-row { display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.btn {
  padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px;
  font-weight: 500; cursor: pointer; transition: all 0.2s; display: inline-flex;
  align-items: center; gap: 6px;
}
.btn-primary { background: #667eea; color: #fff; }
.btn-primary:hover { background: #5568d3; }
.btn-primary:disabled { background: #b0b8d6; cursor: not-allowed; }
.btn-secondary { background: #f0f2f5; color: #333; }
.btn-secondary:hover { background: #e0e3eb; }
.btn-success { background: #52c41a; color: #fff; }
.btn-success:hover { background: #46a814; }
.stats-bar {
  display: flex; gap: 20px; margin: 16px 0; flex-wrap: wrap;
}
.stat-item {
  background: #f8f9fa; padding: 8px 16px; border-radius: 8px;
  font-size: 13px; display: flex; align-items: center; gap: 6px;
}
.stat-item .label { color: #666; }
.stat-item .value { font-weight: 600; color: #1a1a2e; }
.progress-wrap {
  background: #e0e0e0; border-radius: 8px; height: 8px;
  overflow: hidden; margin: 12px 0; display: none;
}
.progress-bar {
  height: 100%; background: linear-gradient(90deg, #667eea, #764ba2);
  width: 0%; transition: width 0.3s; border-radius: 8px;
}
.status-log {
  font-size: 13px; color: #666; margin: 8px 0; min-height: 20px;
}
.status-log .phase { color: #667eea; font-weight: 500; }
table {
  width: 100%; border-collapse: collapse; font-size: 13px;
  table-layout: fixed;
}
th, td {
  padding: 8px 10px; text-align: left; border-bottom: 1px solid #f0f0f0;
  word-break: break-all; overflow: hidden; text-overflow: ellipsis;
}
th {
  background: #fafafa; font-weight: 600; color: #1a1a2e;
  position: sticky; top: 0; z-index: 1;
}
th:first-child, td:first-child { width: 50px; text-align: center; }
tr:hover td { background: #f8f9ff; }
.status-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 500; white-space: nowrap;
}
.status-complete { background: #d4edda; color: #155724; }
.status-partial { background: #fff3cd; color: #856404; }
.status-partial-nocas { background: #cce5ff; color: #004085; }
.status-fail { background: #f8d7da; color: #721c24; }
.table-wrap {
  max-height: 500px; overflow: auto; border: 1px solid #f0f0f0;
  border-radius: 8px; display: none; margin-top: 16px;
}
.empty-hint {
  text-align: center; color: #999; padding: 40px; font-size: 14px;
}
.source-tag {
  display: inline-block; padding: 1px 6px; border-radius: 3px;
  font-size: 11px; background: #e8eaf6; color: #3f51b5; margin: 1px;
}
.footer { text-align: center; color: #999; font-size: 12px; padding: 20px 0; }
th:nth-child(2), td:nth-child(2) { width: 130px; text-align: center; }
td img { border-radius: 4px; }
/* ── 悬停浮动大图 ── */
.struct-tooltip { display: none; position: fixed; z-index: 3000; pointer-events: none; background: #fff; border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.3); padding: 4px; }
.struct-tooltip img { max-width: 300px; max-height: 300px; border-radius: 6px; display: block; }
.struct-tooltip .struct-tooltip-label { font-size: 12px; color: #666; text-align: center; padding: 2px 4px 4px; }
/* ── 结构式灯箱 ── */
.struct-lightbox { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.75); z-index: 2000; justify-content: center; align-items: center; cursor: pointer; overflow: hidden; }
.struct-lightbox.active { display: flex; }
.struct-lightbox img { max-width: 90%; max-height: 90%; border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.4); transform-origin: center center; transition: transform 0.1s ease; }
.struct-lightbox .struct-lightbox-label { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); color: #fff; font-size: 14px; background: rgba(0,0,0,0.6); padding: 8px 16px; border-radius: 6px; }
.struct-lightbox .struct-lightbox-zoom { position: fixed; top: 16px; right: 24px; color: #fff; font-size: 13px; background: rgba(0,0,0,0.5); padding: 6px 12px; border-radius: 6px; }
/* ── 历史记录弹窗 ── */
.modal-overlay {
  display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center;
}
.modal-overlay.active { display: flex; }
.modal-box {
  background: #fff; border-radius: 12px; width: 90%; max-width: 900px; max-height: 85vh;
  display: flex; flex-direction: column; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center; padding: 16px 24px;
  border-bottom: 1px solid #f0f0f0; flex-shrink: 0;
}
.modal-header h2 { font-size: 18px; color: #1a1a2e; }
.modal-close {
  background: none; border: none; font-size: 22px; cursor: pointer; color: #999;
  width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center;
}
.modal-close:hover { background: #f0f2f5; color: #333; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 24px; }
.modal-footer { padding: 12px 24px; border-top: 1px solid #f0f0f0; flex-shrink: 0; text-align: right; }
.hist-empty { text-align: center; color: #999; padding: 40px; font-size: 14px; }
.hist-item {
  display: flex; align-items: center; padding: 12px 16px; border-radius: 8px;
  margin-bottom: 8px; background: #f8f9fa; transition: background 0.2s; gap: 12px;
}
.hist-item:hover { background: #f0f4ff; }
.hist-time { font-size: 13px; color: #667eea; font-weight: 500; white-space: nowrap; min-width: 140px; }
.hist-count { font-size: 13px; color: #333; min-width: 80px; }
.hist-preview { font-size: 12px; color: #999; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hist-stats { display: flex; gap: 8px; font-size: 12px; }
.hist-stats span { padding: 1px 6px; border-radius: 3px; }
.hist-stats .s-ok { background: #d4edda; color: #155724; }
.hist-stats .s-partial { background: #fff3cd; color: #856404; }
.hist-stats .s-fail { background: #f8d7da; color: #721c24; }
.hist-actions { display: flex; gap: 6px; }
.hist-btn {
  padding: 4px 10px; border: none; border-radius: 4px; font-size: 12px;
  cursor: pointer; transition: all 0.2s;
}
.hist-btn-view { background: #667eea; color: #fff; }
.hist-btn-view:hover { background: #5568d3; }
.hist-btn-dl { background: #52c41a; color: #fff; }
.hist-btn-dl:hover { background: #46a814; }
.hist-btn-del { background: #f5222d; color: #fff; }
.hist-btn-del:hover { background: #d4380d; }
.hist-detail-meta { margin-bottom: 16px; font-size: 13px; color: #666; }
</style>
<script>
// SmilesDrawer CDN 加载（纯JS，无需WASM，~100KB，默认CPK着色）
var smilesDrawerLoaded = false;
var smilesDrawerPromise = null;
(function() {
  function loadScript(url) {
    return new Promise(function(resolve, reject) {
      var s = document.createElement('script');
      s.src = url;
      s.onload = function() { resolve(url); };
      s.onerror = function() { reject(new Error('Failed: ' + url)); };
      document.head.appendChild(s);
    });
  }
  var primary = 'https://cdn.jsdelivr.net/npm/smiles-drawer@2.4.1/dist/smiles-drawer.min.js';
  var fallback = 'https://unpkg.com/smiles-drawer@2.4.1/dist/smiles-drawer.min.js';
  smilesDrawerPromise = loadScript(primary)
    .then(function() {
      smilesDrawerLoaded = true;
      console.log('[SmilesDrawer] loaded from jsdelivr');
    })
    .catch(function() {
      console.log('[SmilesDrawer] jsdelivr failed, trying unpkg...');
      return loadScript(fallback).then(function() {
        smilesDrawerLoaded = true;
        console.log('[SmilesDrawer] loaded from unpkg');
      });
    })
    .catch(function() {
      console.log('[SmilesDrawer] All CDNs failed, structure rendering unavailable');
    });
})();
</script>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🔬 化合物结构信息查询工具</h1>
    <p>支持中英文名称 / SMILES / Excel 上传 · 输出 SMILES / CAS / IUPAC / 分子式 / 分子量 / InChIKey / 结构式图片</p>
  </div>

  <div class="card">
    <div class="card-title">输入化合物列表</div>
    <textarea id="input" placeholder="每行一个化合物名称或 SMILES，也可用逗号分隔&#10;&#10;示例：&#10;阿司匹林&#10;osimertinib&#10;CC(=O)Oc1ccccc1C(=O)O"></textarea>
    <div class="btn-row">
      <button class="btn btn-primary" id="btn-query" onclick="startQuery()">▶ 开始查询</button>
      <button class="btn btn-secondary" id="btn-clear" onclick="clearAll()">清空</button>
      <button class="btn btn-secondary" id="btn-upload" onclick="document.getElementById('file-input').click()">📁 上传 Excel</button>
      <input type="file" id="file-input" accept=".xlsx,.xls" style="display:none" onchange="uploadExcel(this)">
      <button class="btn btn-secondary" id="btn-history" onclick="showHistory()">📋 历史记录</button>
      <span style="flex:1"></span>
      <button class="btn btn-success" id="btn-csv" onclick="downloadFile('csv')" style="display:none">⬇ 下载 CSV</button>
      <button class="btn btn-success" id="btn-json" onclick="downloadFile('json')" style="display:none">⬇ 下载 JSON</button>
    </div>
    <div id="upload-status" style="font-size:13px;color:#666;margin-top:8px;display:none"></div>
  </div>

  <div class="card" id="result-card" style="display:none">
    <div class="card-title">查询结果</div>
    <div class="stats-bar" id="stats-bar"></div>
    <div class="progress-wrap" id="progress-wrap">
      <div class="progress-bar" id="progress-bar"></div>
    </div>
    <div class="status-log" id="status-log"></div>
    <div class="table-wrap" id="table-wrap">
      <table id="result-table">
        <thead>
          <tr>
            <th>#</th>
            <th>结构式</th>
            <th>原始输入</th>
            <th>英文名称</th>
            <th>SMILES</th>
            <th>CAS号</th>
            <th>IUPAC名称</th>
            <th>分子式</th>
            <th>分子量</th>
            <th>InChIKey</th>
            <th>数据来源</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody id="result-tbody"></tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    化合物结构信息查询工具 v3.5.7 · 数据源: NCI CACTUS / PubChem / NIST / Wikidata · SmilesDrawer CPK着色渲染（Kekulé双键+白底+宽间距） · Excel 上传 · 历史记录 · 结构式灯箱 · 无需 API Key
  </div>
</div>

<!-- 悬停浮动大图 -->
<div class="struct-tooltip" id="struct-tooltip">
  <img id="struct-tooltip-img" src="" alt="结构式">
  <div class="struct-tooltip-label" id="struct-tooltip-label"></div>
</div>
<!-- 结构式灯箱 -->
<div class="struct-lightbox" id="struct-lightbox" onclick="closeStructLightbox()">
  <img id="struct-lightbox-img" src="" alt="结构式">
  <div class="struct-lightbox-zoom" id="struct-lightbox-zoom">100%</div>
  <div class="struct-lightbox-label" id="struct-lightbox-label"></div>
</div>

<!-- 历史记录弹窗 -->
<div class="modal-overlay" id="hist-modal" onclick="if(event.target===this)closeHistoryModal()">
  <div class="modal-box">
    <div class="modal-header">
      <h2>📋 历史记录</h2>
      <button class="modal-close" onclick="closeHistoryModal()">×</button>
    </div>
    <div class="modal-body" id="hist-modal-body">
      <div class="hist-empty">加载中...</div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeHistoryModal()">关闭</button>
    </div>
  </div>
</div>

<!-- 历史详情弹窗（嵌套） -->
<div class="modal-overlay" id="hist-detail-modal" onclick="if(event.target===this)closeHistDetail()">
  <div class="modal-box" style="max-width:1100px">
    <div class="modal-header">
      <h2 id="hist-detail-title">查询详情</h2>
      <button class="modal-close" onclick="closeHistDetail()">×</button>
    </div>
    <div class="modal-body" id="hist-detail-body">
      <div class="hist-empty">加载中...</div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-success" onclick="downloadHist('csv')">⬇ CSV</button>
      <button class="btn btn-success" onclick="downloadHist('json')">⬇ JSON</button>
      <button class="btn btn-secondary" onclick="closeHistDetail()">关闭</button>
    </div>
  </div>
</div>

<script>
// ── SmilesDrawer 客户端结构式渲染（三级兜底）──
// Tier 1: PubChem PNG（有 CID 时直接用官方图片）
// Tier 2: SmilesDrawer Canvas（有 SMILES 时纯JS渲染，CPK着色）
// Tier 3: CACTUS PNG（SmilesDrawer 不可用或渲染失败时的网络兜底）
var smilesDrawerInstance = null;
var smilesDrawerInitPromise = null;

function ensureSmilesDrawer() {
  if (smilesDrawerInitPromise) return smilesDrawerInitPromise;
  smilesDrawerInitPromise = (smilesDrawerPromise || Promise.resolve()).then(function() {
    // v2.x API: SmiDrawer class
    if (typeof SmiDrawer !== 'undefined') {
      smilesDrawerInstance = new SmiDrawer({
        width: 500, height: 500, bondThickness: 1.8,
        shortBondLength: 0.85, bondSpacing: 6,
        atomVisualization: 'default', isomeric: true,
        debug: false, terminalCarbons: false, explicitHydrogens: false,
        compactDrawing: false, fontSizeLarge: 11, fontSizeSmall: 3, padding: 12,
        bondColor: '#222', backgroundFillColor: '#ffffff',
        themes: { light: {
          C: '#222', O: '#e00e0e', N: '#3050f8', F: '#1ff01f',
          CL: '#1ff01f', BR: '#a62929', I: '#9c09d7', P: '#ff8000',
          S: '#e6c200', B: '#ffb5b5', SI: '#f0c8a0', H: '#cccccc', BACKGROUND: '#ffffff'
        }}
      });
      console.log('[SmilesDrawer] ready (v2 SmiDrawer)');
      return smilesDrawerInstance;
    }
    // v1.x API: SmilesDrawer.Drawer + SmilesDrawer.parse
    if (typeof SmilesDrawer !== 'undefined' && SmilesDrawer.Drawer) {
      smilesDrawerInstance = {
        draw: function(smiles, selector, theme) {
          var drawer = new SmilesDrawer.Drawer({
            width: 500, height: 500, bondThickness: 1.8,
            shortBondLength: 0.85, bondSpacing: 6,
            atomVisualization: 'default', isomeric: true,
            compactDrawing: false, fontSizeLarge: 11, fontSizeSmall: 3, padding: 12,
            bondColor: '#222', backgroundFillColor: '#ffffff'
          });
          SmilesDrawer.parse(smiles, function(tree) {
            drawer.draw(tree, selector.replace('#', ''), theme, false);
          });
        }
      };
      console.log('[SmilesDrawer] ready (v1 SmilesDrawer)');
      return smilesDrawerInstance;
    }
    console.log('[SmilesDrawer] not available');
    return null;
  }).catch(function(e) {
    console.log('[SmilesDrawer] init failed:', e);
    return null;
  });
  return smilesDrawerInitPromise;
}

function kekulizeSmiles(smiles) {
  if (!smiles || !/[cnopsb]/.test(smiles)) return smiles;
  var result = '', i = 0, toggle = true, lastAromatic = false;
  var branchStack = [];
  while (i < smiles.length) {
    var ch = smiles[i];
    // Bracket atom [nH] [n+] [c-]
    if (ch === '[') {
      var ci = smiles.indexOf(']', i);
      if (ci > 0) {
        var bc = smiles.substring(i, ci + 1);
        var fa = bc.match(/[cnopsb]/);
        if (fa) {
          bc = bc.replace(fa[0], fa[0].toUpperCase());
          if (lastAromatic) { if (toggle) result += '='; toggle = !toggle; }
          lastAromatic = true;
        } else { if (lastAromatic) toggle = true; lastAromatic = false; }
        result += bc; i = ci + 1; continue;
      }
    }
    // Two-letter atoms Cl Br Si
    if (i + 1 < smiles.length && /[A-Z]/.test(ch) && /[a-z]/.test(smiles[i+1]) && !/[cnopsb]/.test(smiles[i+1])) {
      if (lastAromatic) toggle = true;
      result += ch + smiles[i+1]; lastAromatic = false; i += 2; continue;
    }
    // Aromatic atom
    if (/[cnopsb]/.test(ch)) {
      if (lastAromatic) { if (toggle) result += '='; toggle = !toggle; }
      result += ch.toUpperCase(); lastAromatic = true; i++; continue;
    }
    // Ring closure (% for >9)
    if (ch === '%' && i + 2 < smiles.length) { result += smiles.substring(i, i+3); i += 3; continue; }
    if (/\d/.test(ch)) { result += ch; i++; continue; }
    // Branch
    if (ch === '(') { branchStack.push({t: toggle, a: lastAromatic}); result += ch; i++; continue; }
    if (ch === ')') {
      if (branchStack.length > 0) { var sv = branchStack.pop(); lastAromatic = sv.a; toggle = sv.t; }
      result += ch; i++; continue;
    }
    if (ch === ':') { i++; continue; }
    if (/[=#\-\/\\]/.test(ch)) { if (lastAromatic) toggle = true; result += ch; lastAromatic = false; i++; continue; }
    if (/[A-Z]/.test(ch)) { if (lastAromatic) toggle = true; lastAromatic = false; }
    result += ch; i++;
  }
  return result;
}

function renderStructWithSmilesDrawer(smiles, container, size, label) {
  if (!smilesDrawerInstance || !smiles) return false;
  try {
    var canvasId = 'sd-' + Math.random().toString(36).substr(2, 9);
    container.innerHTML = '<canvas id="' + canvasId + '" width="' + size + '" height="' + size + '" style="max-width:100%;max-height:100%;background:#ffffff;border-radius:4px"></canvas>';
    var kekSmiles = kekulizeSmiles(smiles);
    smilesDrawerInstance.draw(kekSmiles, '#' + canvasId, 'light');
    // Wait for async rendering, then convert canvas to data URL for hover/lightbox
    setTimeout(function() {
      var canvas = document.getElementById(canvasId);
      if (!canvas) return;
      try {
        // 白色背景填充（destination-over: 在已有绘图下方填充，不覆盖）
        var ctx = canvas.getContext('2d');
        ctx.globalCompositeOperation = 'destination-over';
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.globalCompositeOperation = 'source-over';
        var dataUrl = canvas.toDataURL('image/png');
        if (dataUrl && dataUrl.length > 1000) {
          container.onmouseover = function(e) { showStructTooltip(dataUrl, label, e); };
          container.onmousemove = moveStructTooltip;
          container.onmouseout = hideStructTooltip;
          container.onclick = function() { openStructLightbox(dataUrl, label); };
        }
      } catch(e) { console.log('[SmilesDrawer] canvas conversion error:', e); }
    }, 200);
    return true;
  } catch(e) {
    console.log('[SmilesDrawer] render error:', e);
    return false;
  }
}

function createStructHtml(row, size) {
  var label = escapeHtml(row['英文名称'] || row['原始输入'] || '');
  var smiles = row['SMILES'] || '';
  var imgUrl = row['结构图片'] || '';

  if (!smiles && !imgUrl) return '—';

  // 统一渲染管线：先用网络图片占位，再尝试 RDKit.js SVG 替换（所有化合物都走这条路）
  var id = 'struct-' + Math.random().toString(36).substr(2, 9);
  var html = '<div id="' + id + '" style="display:flex;align-items:center;justify-content:center;width:' + size + 'px;height:' + size + 'px;margin:0 auto;cursor:pointer">';
  if (imgUrl) {
    html += '<img src="' + imgUrl + '" style="max-width:' + size + 'px;max-height:' + size + 'px;border-radius:4px" loading="lazy" onerror="this.style.display=\'none\'">';
  } else {
    html += '<span style="color:#bbb;font-size:11px">渲染中…</span>';
  }
  html += '</div>';

  setTimeout(function() {
    var container = document.getElementById(id);
    if (!container) return;

    // 先绑定兜底图事件
    var imgEl = container.querySelector('img');
    if (imgEl && imgUrl) {
      container.onmouseover = function(e) { showStructTooltip(imgUrl, label, e); };
      container.onmousemove = moveStructTooltip;
      container.onmouseout = hideStructTooltip;
      container.onclick = function() { openStructLightbox(imgUrl, label); };
    }

    // 尝试 SmilesDrawer Canvas 渲染（有 SMILES 就试，不管是否有 CID）
    if (smiles) {
      ensureSmilesDrawer().then(function() {
        if (!renderStructWithSmilesDrawer(smiles, container, size, label)) return;
        // SmilesDrawer 渲染成功，事件已在 renderStructWithSmilesDrawer 中更新
      });
    }
  }, 80);
  return html;
}

let currentTaskId = null;
let queryResults = [];
let eventSource = null;

function startQuery() {
  const input = document.getElementById('input').value.trim();
  if (!input) { alert('请先输入化合物列表'); return; }

  // 重置 UI
  document.getElementById('btn-query').disabled = true;
  document.getElementById('btn-query').textContent = '⏳ 查询中...';
  document.getElementById('result-card').style.display = 'block';
  document.getElementById('table-wrap').style.display = 'block';
  document.getElementById('progress-wrap').style.display = 'block';
  document.getElementById('btn-csv').style.display = 'none';
  document.getElementById('btn-json').style.display = 'none';
  document.getElementById('result-tbody').innerHTML = '';
  document.getElementById('stats-bar').innerHTML = '';
  queryResults = [];

  // 发起 SSE 请求
  eventSource = new EventSource('/api/query?' + new URLSearchParams({
    compounds: input
  }));

  // 由于 EventSource 不支持 POST，改用 fetch + ReadableStream
  eventSource.close();
  fetchSSE(input);
}

async function fetchSSE(input) {
  const response = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ compounds: input })
  });

  if (!response.ok) {
    const err = await response.json();
    alert(err.error || '查询失败');
    resetButtons();
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    let eventType = 'message';
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        handleSSE(eventType, data);
        eventType = 'message';
      }
    }
  }
  resetButtons();
}

function handleSSE(type, data) {
  if (type === 'error') {
    document.getElementById('status-log').innerHTML =
      '<span style="color:#e74c3c">❌ ' + (data.error || '查询出错') + '</span>';
    return;
  }

  if (type === 'done') {
    currentTaskId = data.task_id;
    document.getElementById('progress-bar').style.width = '100%';
    document.getElementById('status-log').innerHTML =
      '<span class="phase">✅ 全部查询完成</span>';
    document.getElementById('btn-csv').style.display = 'inline-flex';
    document.getElementById('btn-json').style.display = 'inline-flex';
    updateStats();
    return;
  }

  // 进度消息
  const { current, total, name, row, phase } = data;

  if (phase === 'querying') {
    document.getElementById('status-log').innerHTML =
      '<span class="phase">🔍 正在查询</span> [' + current + '/' + total + '] ' + escapeHtml(name);
  }

  if (phase === 'enriching') {
    document.getElementById('status-log').innerHTML =
      '<span class="phase">📋 富集中</span> ' + escapeHtml(name);
  }

  if (phase === 'done' && row) {
    queryResults.push(row);
    addTableRow(queryResults.length, row);
    const pct = Math.round((current / total) * 100);
    document.getElementById('progress-bar').style.width = pct + '%';
    updateStats();
  }
}

function addTableRow(idx, row) {
  const tbody = document.getElementById('result-tbody');
  const tr = document.createElement('tr');
  const statusClass = row['状态'] === '完整' ? 'status-complete'
    : row['状态'] === '部分' ? 'status-partial'
    : row['状态'] === '部分(CAS未注册)' ? 'status-partial-nocas'
    : 'status-fail';
  const sources = (row['数据来源'] || '').split('+').map(s =>
    '<span class="source-tag">' + escapeHtml(s) + '</span>').join('');
  const imgHtml = createStructHtml(row, 120);
  tr.innerHTML =
    '<td>' + idx + '</td>'
    + '<td style="text-align:center">' + imgHtml + '</td>'
    + '<td>' + escapeHtml(row['原始输入'] || '') + '</td>'
    + '<td>' + escapeHtml(row['英文名称'] || '') + '</td>'
    + '<td style="font-size:12px">' + escapeHtml(row['SMILES'] || '') + '</td>'
    + '<td>' + escapeHtml(row['CAS号'] || '') + '</td>'
    + '<td style="font-size:12px">' + escapeHtml(row['IUPAC名称'] || '') + '</td>'
    + '<td>' + escapeHtml(row['分子式'] || '') + '</td>'
    + '<td>' + escapeHtml(row['分子量'] || '') + '</td>'
    + '<td style="font-size:12px">' + escapeHtml(row['InChIKey'] || '') + '</td>'
    + '<td>' + sources + '</td>'
    + '<td><span class="status-badge ' + statusClass + '">' + (row['状态'] || '') + '</span></td>';
  tbody.appendChild(tr);
}

function updateStats() {
  const total = queryResults.length;
  const complete = queryResults.filter(r => r['状态'] === '完整').length;
  const partial = queryResults.filter(r => r['状态'] === '部分').length;
  const partialNoCas = queryResults.filter(r => r['状态'] === '部分(CAS未注册)').length;
  const fail = queryResults.filter(r => r['状态'] === '失败').length;
  document.getElementById('stats-bar').innerHTML =
    statItem('总计', total)
    + statItem('完整', complete, '#52c41a')
    + statItem('部分', partial, '#faad14')
    + statItem('CAS未注册', partialNoCas, '#1890ff')
    + statItem('失败', fail, '#f5222d');
}

function statItem(label, value, color) {
  const c = color ? ' style="color:' + color + '"' : '';
  return '<div class="stat-item"><span class="label">' + label + ':</span><span class="value"' + c + '>' + value + '</span></div>';
}

function resetButtons() {
  document.getElementById('btn-query').disabled = false;
  document.getElementById('btn-query').textContent = '▶ 开始查询';
}

function clearAll() {
  document.getElementById('input').value = '';
  document.getElementById('result-card').style.display = 'none';
  queryResults = [];
  currentTaskId = null;
}

function downloadFile(fmt) {
  if (!currentTaskId) return;
  window.location.href = '/api/download/' + currentTaskId + '/' + fmt;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function uploadExcel(input) {
  const file = input.files[0];
  if (!file) return;
  const statusEl = document.getElementById('upload-status');
  statusEl.style.display = 'block';
  statusEl.textContent = '📁 正在解析 ' + file.name + ' ...';
  statusEl.style.color = '#667eea';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await resp.json();
    if (!resp.ok) {
      statusEl.textContent = '❌ ' + (data.error || '解析失败');
      statusEl.style.color = '#e74c3c';
      return;
    }
    const compounds = data.compounds || [];
    document.getElementById('input').value = compounds.join('\n');
    statusEl.textContent = '✅ 已从 Excel 导入 ' + compounds.length + ' 个化合物';
    statusEl.style.color = '#52c41a';
  } catch (e) {
    statusEl.textContent = '❌ 上传失败: ' + e.message;
    statusEl.style.color = '#e74c3c';
  }
  input.value = '';
}
// ── 历史记录功能 ──
let currentHistFile = null;

async function showHistory() {
  document.getElementById('hist-modal').classList.add('active');
  document.getElementById('hist-modal-body').innerHTML = '<div class="hist-empty">加载中...</div>';
  try {
    const resp = await fetch('/api/history');
    const data = await resp.json();
    const records = data.history || [];
    if (records.length === 0) {
      document.getElementById('hist-modal-body').innerHTML =
        '<div class="hist-empty">暂无历史记录<br><span style="font-size:12px;color:#bbb">查询完成后会自动保存到 exe 同目录的 history/ 文件夹</span></div>';
      return;
    }
    let html = '<div style="margin-bottom:12px;font-size:13px;color:#666">共 ' + records.length + ' 条记录，按时间倒序排列</div>';
    for (const r of records) {
      const s = r.summary || {};
      const statsHtml = '<div class="hist-stats">'
        + (s.complete ? '<span class="s-ok">完整 ' + s.complete + '</span>' : '')
        + (s.partial + s.partial_nocas ? '<span class="s-partial">部分 ' + (s.partial + s.partial_nocas) + '</span>' : '')
        + (s.fail ? '<span class="s-fail">失败 ' + s.fail + '</span>' : '')
        + '</div>';
      html += '<div class="hist-item">'
        + '<span class="hist-time">' + escapeHtml(r.timestamp_display || r.timestamp) + '</span>'
        + '<span class="hist-count">' + (r.compound_count || 0) + ' 个化合物</span>'
        + statsHtml
        + '<span class="hist-preview">' + escapeHtml(r.compounds_preview || '') + '</span>'
        + '<div class="hist-actions">'
        + '<button class="hist-btn hist-btn-view" onclick="viewHistDetail(\'' + r.filename + '\')">查看</button>'
        + '<button class="hist-btn hist-btn-dl" onclick="downloadHistFile(\'' + r.filename + '\',\'csv\')">CSV</button>'
        + '<button class="hist-btn hist-btn-dl" onclick="downloadHistFile(\'' + r.filename + '\',\'json\')">JSON</button>'
        + '<button class="hist-btn hist-btn-del" onclick="deleteHistFile(\'' + r.filename + '\')">删除</button>'
        + '</div>'
        + '</div>';
    }
    document.getElementById('hist-modal-body').innerHTML = html;
  } catch (e) {
    document.getElementById('hist-modal-body').innerHTML =
      '<div class="hist-empty" style="color:#e74c3c">加载失败: ' + escapeHtml(e.message) + '</div>';
  }
}

function closeHistoryModal() {
  document.getElementById('hist-modal').classList.remove('active');
}

async function viewHistDetail(filename) {
  currentHistFile = filename;
  document.getElementById('hist-detail-modal').classList.add('active');
  document.getElementById('hist-detail-body').innerHTML = '<div class="hist-empty">加载中...</div>';
  try {
    const resp = await fetch('/api/history/' + filename);
    const data = await resp.json();
    if (!resp.ok) {
      document.getElementById('hist-detail-body').innerHTML =
        '<div class="hist-empty" style="color:#e74c3c">' + escapeHtml(data.error || '加载失败') + '</div>';
      return;
    }
    const meta = data.meta || {};
    const results = data.results || [];
    document.getElementById('hist-detail-title').textContent =
      '查询详情 · ' + (meta.timestamp_display || filename);

    const s = meta.summary || {};
    let html = '<div class="hist-detail-meta">'
      + '时间: ' + escapeHtml(meta.timestamp_display || '') + ' · '
      + '化合物数: ' + (meta.compound_count || 0) + ' · '
      + '完整: ' + (s.complete || 0) + ' · 部分: ' + ((s.partial || 0) + (s.partial_nocas || 0)) + ' · 失败: ' + (s.fail || 0)
      + '</div>';

    html += '<div class="table-wrap" style="display:block;max-height:400px"><table><thead><tr>'
      + '<th>#</th><th>结构式</th><th>原始输入</th><th>英文名称</th><th>SMILES</th>'
      + '<th>CAS号</th><th>IUPAC名称</th><th>分子式</th><th>分子量</th><th>InChIKey</th>'
      + '<th>数据来源</th><th>状态</th>'
      + '</tr></thead><tbody>';

    results.forEach((row, i) => {
      const statusClass = row['状态'] === '完整' ? 'status-complete'
        : row['状态'] === '部分' ? 'status-partial'
        : row['状态'] === '部分(CAS未注册)' ? 'status-partial-nocas'
        : 'status-fail';
      const sources = (row['数据来源'] || '').split('+').map(s2 =>
        '<span class="source-tag">' + escapeHtml(s2) + '</span>').join('');
      const imgHtml = createStructHtml(row, 80);
      html += '<tr>'
        + '<td>' + (i + 1) + '</td>'
        + '<td style="text-align:center">' + imgHtml + '</td>'
        + '<td>' + escapeHtml(row['原始输入'] || '') + '</td>'
        + '<td>' + escapeHtml(row['英文名称'] || '') + '</td>'
        + '<td style="font-size:12px">' + escapeHtml(row['SMILES'] || '') + '</td>'
        + '<td>' + escapeHtml(row['CAS号'] || '') + '</td>'
        + '<td style="font-size:12px">' + escapeHtml(row['IUPAC名称'] || '') + '</td>'
        + '<td>' + escapeHtml(row['分子式'] || '') + '</td>'
        + '<td>' + escapeHtml(row['分子量'] || '') + '</td>'
        + '<td style="font-size:12px">' + escapeHtml(row['InChIKey'] || '') + '</td>'
        + '<td>' + sources + '</td>'
        + '<td><span class="status-badge ' + statusClass + '">' + (row['状态'] || '') + '</span></td>'
        + '</tr>';
    });
    html += '</tbody></table></div>';
    document.getElementById('hist-detail-body').innerHTML = html;
  } catch (e) {
    document.getElementById('hist-detail-body').innerHTML =
      '<div class="hist-empty" style="color:#e74c3c">加载失败: ' + escapeHtml(e.message) + '</div>';
  }
}

function closeHistDetail() {
  document.getElementById('hist-detail-modal').classList.remove('active');
}

function downloadHist(fmt) {
  if (!currentHistFile) return;
  downloadHistFile(currentHistFile, fmt);
}

function downloadHistFile(filename, fmt) {
  window.location.href = '/api/history/' + filename + '/download/' + fmt;
}

async function deleteHistFile(filename) {
  if (!confirm('确认删除这条历史记录？此操作不可撤销。')) return;
  try {
    const resp = await fetch('/api/history/' + filename, { method: 'DELETE' });
    const data = await resp.json();
    if (resp.ok) {
      showHistory();
    } else {
      alert(data.error || '删除失败');
    }
  } catch (e) {
    alert('删除失败: ' + e.message);
  }
}
function openStructLightbox(src, label) {
  var lb = document.getElementById('struct-lightbox');
  var img = document.getElementById('struct-lightbox-img');
  var lbl = document.getElementById('struct-lightbox-label');
  var zoom = document.getElementById('struct-lightbox-zoom');
  img.src = src;
  lbl.textContent = label || '';
  lb.classList.add('active');
  lb.dataset.scale = '1';
  img.style.transform = 'scale(1)';
  zoom.textContent = '100%';
}
function closeStructLightbox() {
  var lb = document.getElementById('struct-lightbox');
  lb.classList.remove('active');
  lb.dataset.scale = '1';
  document.getElementById('struct-lightbox-img').style.transform = 'scale(1)';
}
document.addEventListener('wheel', function(e) {
  var lb = document.getElementById('struct-lightbox');
  if (!lb.classList.contains('active')) return;
  if (lb.contains(e.target) || e.target === lb) {
    e.preventDefault();
    var img = document.getElementById('struct-lightbox-img');
    var scale = parseFloat(lb.dataset.scale || '1');
    if (e.deltaY < 0) { scale = Math.min(scale + 0.15, 5); }
    else { scale = Math.max(scale - 0.15, 0.3); }
    lb.dataset.scale = scale;
    img.style.transform = 'scale(' + scale + ')';
    document.getElementById('struct-lightbox-zoom').textContent = Math.round(scale * 100) + '%';
  }
}, { passive: false });
function showStructTooltip(src, label, e) {
  var tip = document.getElementById('struct-tooltip');
  var img = document.getElementById('struct-tooltip-img');
  var lbl = document.getElementById('struct-tooltip-label');
  img.src = src;
  lbl.textContent = label || '';
  tip.style.display = 'block';
  moveStructTooltip(e);
}
function moveStructTooltip(e) {
  var tip = document.getElementById('struct-tooltip');
  var w = tip.offsetWidth, h = tip.offsetHeight;
  var x = e.clientX + 16, y = e.clientY + 16;
  if (x + w > window.innerWidth) x = e.clientX - w - 16;
  if (y + h > window.innerHeight) y = e.clientY - h - 16;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}
function hideStructTooltip() {
  document.getElementById('struct-tooltip').style.display = 'none';
}
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

def open_browser(host, port):
    """延迟 1.5 秒打开浏览器，等待 Flask 启动"""
    time.sleep(1.5)
    webbrowser.open(f"http://{host}:{port}")


def main():
    host = "127.0.0.1"
    port = 5173

    print("=" * 60)
    print("  化合物结构信息查询工具 v3.5-exe")
    print("  Web UI: http://{}:{}".format(host, port))
    print("  按 Ctrl+C 退出")
    print("=" * 60)

    # 自动打开浏览器
    threading.Thread(target=open_browser, args=(host, port), daemon=True).start()

    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
