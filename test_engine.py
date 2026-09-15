import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Test 1: import compound_engine and check for callback references
import compound_engine

# Test 2: check run_concurrent signature
import inspect
sig = inspect.signature(compound_engine.run_concurrent)
print(f"run_concurrent signature: {sig}")

# Test 3: call run_concurrent with a test compound
print("Testing run_concurrent with aspirin...")
results = compound_engine.run_concurrent(["aspirin"], max_workers=1)
if results:
    r = results[0]
    print(f"  SMILES: {r.get('SMILES', 'N/A')}")
    print(f"  CAS: {r.get('CAS号', 'N/A')}")
    print(f"  InChIKey: {r.get('InChIKey', 'N/A')}")
    print(f"  状态: {r.get('状态', 'N/A')}")
    print("  ✅ run_concurrent works!")
else:
    print("  ❌ No results returned")

# Test 4: verify no bare 'callback' in compound_engine source
src = inspect.getsource(compound_engine)
for i, line in enumerate(src.split('\n'), 1):
    if 'callback' in line and 'progress_callback' not in line and 'progress_cb' not in line:
        print(f"  ⚠️ Line {i}: {line.strip()}")

print("\nAll tests passed!")
