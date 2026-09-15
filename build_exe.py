#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建脚本 — 将 PyInstaller 输出重定向到日志文件"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app.py")
OUT = os.path.join(HERE, "dist")
LOG = os.path.join(HERE, "build_log.txt")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--name", "compound-lookup",
    "--distpath", OUT,
    "--workpath", os.path.join(HERE, "build"),
    "--specpath", HERE,
    "--collect-data", "openpyxl",
    "--hidden-import", "openpyxl",
    "--hidden-import", "requests",
    "--hidden-import", "rdkit",
    "--hidden-import", "rdkit.Chem",
    "--hidden-import", "rdkit.Chem.inchi",
    "--hidden-import", "rdkit.Chem.rdchem",
    "--hidden-import", "rdkit.Chem.rdinchi",
    "--hidden-import", "rdkit.RDPaths",
    "--noconfirm",
    "--clean",
    APP,
]

print("Running PyInstaller...")
with open(LOG, "w", encoding="utf-8") as logf:
    logf.write("CMD: " + " ".join(cmd) + "\n\n")
    logf.flush()
    ret = subprocess.run(cmd, cwd=HERE, stdout=logf, stderr=subprocess.STDOUT)
    logf.write(f"\n\nExit code: {ret.returncode}\n")

print(f"Exit code: {ret.returncode}")
print(f"Log written to: {LOG}")
sys.exit(ret.returncode)
