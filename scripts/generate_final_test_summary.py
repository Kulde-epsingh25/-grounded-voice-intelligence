"""
Generate final test results summary text and json artifacts.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
JUNIT_XML = ROOT_DIR / "evidence" / "pytest_junit.xml"
TXT_OUT = ROOT_DIR / "evidence" / "final_test_results.txt"
JSON_OUT = ROOT_DIR / "evidence" / "final_test_results.json"

tree = ET.parse(JUNIT_XML)
root = tree.getroot()

testsuite = root.find("testsuite") or root

total = int(testsuite.attrib.get("tests", 0))
failures = int(testsuite.attrib.get("failures", 0))
errors = int(testsuite.attrib.get("errors", 0))
skipped = int(testsuite.attrib.get("skipped", 0))
time_s = float(testsuite.attrib.get("time", 0.0))
passed = total - failures - errors - skipped

summary = {
    "total": total,
    "passed": passed,
    "failed": failures + errors,
    "skipped": skipped,
    "duration_seconds": round(time_s, 2),
    "status": "PASS" if (failures + errors) == 0 else "FAIL",
}

with open(JSON_OUT, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

txt_content = f"""AI Engineer Assessment — Final Pytest Results Summary
======================================================
Total Tests:      {total}
Passed:           {passed}
Failed:           {failures + errors}
Skipped:          {skipped}
Execution Time:   {time_s:.2f} seconds
Overall Status:   {summary['status']}
"""

with open(TXT_OUT, "w", encoding="utf-8") as f:
    f.write(txt_content)

print(txt_content)
