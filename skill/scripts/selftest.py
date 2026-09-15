#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — compound-structure-lookup 自检脚本 v1.0
测试已知化合物的查询逻辑和校验函数。
用法: python selftest.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def test_validate_cas():
    """测试 CAS 校验码验证"""
    from compound_lookup import validate_cas
    assert validate_cas('50-78-2'), 'Aspirin CAS should be valid'
    assert validate_cas('156-54-7'), 'CAS 156-54-7 should be valid'
    assert not validate_cas('50-78-3'), 'Wrong check digit should fail'
    assert not validate_cas('abc'), 'Non-numeric should fail'
    assert not validate_cas(''), 'Empty should fail'
    print('[PASS] test_validate_cas')


def test_is_smiles():
    """测试 SMILES 检测"""
    from compound_lookup import is_smiles
    assert is_smiles('CC(=O)Oc1ccccc1C(=O)O'), 'Aspirin SMILES should be detected'
    assert is_smiles('CN1C=NC2=C1C(=O)NC(=O)N2'), 'Caffeine SMILES should be detected'
    assert is_smiles('c1ccccc1'), 'Benzene aromatic SMILES should be detected'
    assert not is_smiles('aspirin'), 'Name should not be detected as SMILES'
    assert not is_smiles(''), 'Empty should not be SMILES'
    assert not is_smiles('ab'), 'Too short should not be SMILES'
    print('[PASS] test_is_smiles')


def test_clean_cas():
    """测试 CAS 提取"""
    from compound_lookup import clean_cas
    cas = clean_cas('CAS: 50-78-2')
    assert cas == '50-78-2', f'Expected 50-78-2, got {cas}'
    cas = clean_cas('50-78-2')
    assert cas == '50-78-2', f'Expected 50-78-2, got {cas}'
    print('[PASS] test_clean_cas')


def test_rdkit_inchikey():
    """测试 RDKit InChIKey 计算"""
    try:
        from compound_lookup import compute_inchikey_local
        ik, _ = compute_inchikey_local('CC(=O)Oc1ccccc1C(=O)O')
        if ik:
            assert len(ik) == 27, f'InChIKey should be 27 chars (14-10-1 format), got {len(ik)}'
            print(f'[PASS] test_rdkit_inchikey (IK={ik})')
        else:
            print('[SKIP] test_rdkit_inchikey (RDKit not available)')
    except ImportError:
        print('[SKIP] test_rdkit_inchikey (RDKit not installed)')


def test_translate_name():
    """测试中文名称翻译"""
    from compound_lookup import translate_name
    assert translate_name('阿司匹林') == 'aspirin', '阿司匹林 should translate to aspirin'
    assert translate_name('布洛芬') == 'ibuprofen', '布洛芬 should translate to ibuprofen'
    assert translate_name('aspirin') == 'aspirin', 'English name should pass through'
    print('[PASS] test_translate_name')


def main():
    print('=== compound-structure-lookup selftest ===')
    tests = [
        test_validate_cas,
        test_is_smiles,
        test_clean_cas,
        test_rdkit_inchikey,
        test_translate_name,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n=== Results: {passed} passed, {failed} failed ===')
    return 1 if failed > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
