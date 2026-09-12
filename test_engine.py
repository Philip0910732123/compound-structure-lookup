#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速功能测试：验证 compound_engine 查询逻辑正常工作"""
import json
import sys
sys.path.insert(0, ".")
from compound_engine import run, export_csv

test_compounds = ["aspirin", "caffeine"]
print(f"测试化合物: {test_compounds}")
print("开始查询...\n")

results = run(test_compounds, progress_callback=lambda c, t, n, r, p: 
    print(f"  [{p}] {c}/{t} {n[:40]}") if p in ('querying', 'done') else None)

print("\n=== 查询结果 ===")
for r in results:
    print(f"\n{r['原始输入']}:")
    print(f"  SMILES:   {r.get('SMILES')}")
    print(f"  CAS:      {r.get('CAS号')}")
    print(f"  IUPAC:    {r.get('IUPAC名称')}")
    print(f"  分子式:   {r.get('分子式')}")
    print(f"  分子量:   {r.get('分子量')}")
    print(f"  InChIKey: {r.get('InChIKey')}")
    print(f"  来源:     {r.get('数据来源')}")
    print(f"  状态:     {r.get('状态')}")

# 验证关键字段
ok = True
for r in results:
    if not r.get('SMILES'):
        print(f"\n[FAIL] {r['原始输入']} 缺少 SMILES")
        ok = False
    if not r.get('CAS号'):
        print(f"\n[WARN] {r['原始输入']} 缺少 CAS号（可能是未注册化合物）")
    if not r.get('InChIKey'):
        print(f"\n[WARN] {r['原始输入']} 缺少 InChIKey")

if ok:
    print("\n✅ 功能测试通过：SMILES 字段全部获取成功")
else:
    print("\n❌ 功能测试存在问题")
    sys.exit(1)
