import json

S = json.load(open("summary.json"))
L = ["L0 clean digital", "L1 good scan", "L2 poor scan", "L3 fax / photocopy"]
NAME = {"L0 clean digital": "Clean digital PDF (300 dpi)", "L1 good scan": "Good scan (200 dpi)",
        "L2 poor scan": "Poor scan (150 dpi, blur, specks)", "L3 fax / photocopy": "Fax or photocopy (150 dpi, black and white)"}


def pct(x, n):
    v = 100 * x / n
    return f"{v:.1f}%" if v else "0%"


rows = []
for lv in L:
    s = S[lv]
    n = s["readers"]["n"]
    c1, c0, fx = s["naive_c1.0"], s["naive_c0.0"], s["fixed"]
    rows.append(
        f"| {NAME[lv]} | {s['readers']['tess_wrong']} of {n} | "
        f"{c1['undetected']} ({c1['undetected_bind']} row slips) | "
        f"{c0['undetected']} / {pct(c0['human'], n)} ({c0['false_alarm']} false alarms) | "
        f"{fx['undetected']} / {pct(fx['human'], n)} |")
table = ("| Scan quality | OCR misreads (Tesseract) | Naive, VLM repeats the OCR: silently wrong | "
         "Naive, independent VLM: silently wrong / sent to a person | Fixed design: silently wrong / sent to a person |\n"
         "|---|---|---|---|---|\n" + "\n".join(rows))
print(table)
tot_fx = sum(S[lv]["fixed"]["undetected"] for lv in L)
print("fixed undetected total", tot_fx)
for lv in L:
    s = S[lv]
    print(lv, "c0.5", s["naive_c0.5"], "same text", s["readers"]["both_same_text"], "grid", S["_grid"][lv],
          "fixed", s["fixed"])
