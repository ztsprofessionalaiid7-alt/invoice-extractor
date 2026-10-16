import json
import time

from pipeline import process as extract_invoice


def same_items(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x["description"].strip().lower() != y["description"].strip().lower():
            return False
        if abs(x["quantity"] - y["quantity"]) > 0.001:
            return False
        if abs(x["unit_price"] - y["unit_price"]) > 0.01:
            return False
    return True


def compare(got, exp):
    bad = []
    for k in ["invoice_number", "date", "vendor", "customer", "currency"]:
        if got[k] != exp[k]:
            bad.append(k)
    gt, et = got["total"], exp["total"]
    if (gt is None) != (et is None) or (gt is not None and abs(gt - et) > 0.01):
        bad.append("total")
    if not same_items(got["line_items"], exp["line_items"]):
        bad.append("line_items")
    if set(got["flags"]) != set(exp["flags"]):
        bad.append("flags")
    return bad


def main():
    rows = [json.loads(l) for l in open("hidden_cases.jsonl", encoding="utf-8")]
    passed = 0
    results = []
    for r in rows:
        try:
            got = extract_invoice(r["input"]).model_dump()
            bad = compare(got, r["expected"])
        except Exception as e:
            got, bad = None, [f"error: {e}"]
        ok = not bad
        passed += ok
        print("PASS" if ok else "FAIL", r["input"], r["tag"], bad)
        results.append({"input": r["input"], "tag": r["tag"], "pass": ok,
                        "bad_fields": bad, "got": got})
        time.sleep(4)  # ফ্রি টিয়ারের গতিসীমা এড়াতে
    print(f"\nHidden: {passed}/{len(rows)}")
    with open("results_hidden.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


main()