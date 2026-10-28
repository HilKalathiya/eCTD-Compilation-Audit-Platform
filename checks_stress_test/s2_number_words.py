"""S2: how many results in a real CSR are written in a form that a digit-only
validator ("every digit traces to a fact") never sees?
Source: CDISC SDTM/ADaM Pilot Project CSR (CDISCPILOT01, final 27 June 2006),
narrative pages only (synopsis pp. 2-6, body pp. 12-41). Read-only."""
import json, re, sys
import pymupdf

PDF = sys.argv[1] if len(sys.argv) > 1 else "csr.pdf"   # CDISC pilot CSR (cdisc-org/sdtm-adam-pilot-project)
PAGES = list(range(2, 7)) + list(range(12, 42))          # 1-based page numbers
JUNK = re.compile(r"^(CDISC SDTM/ADaM Pilot Project|CDISCPILOT01|FINAL CSR|- \d+ -|27 June 2006)\s*$")

doc = pymupdf.open(PDF)
text = []
for p in PAGES:
    lines = [l for l in doc[p - 1].get_text().splitlines() if not JUNK.match(l.strip())]
    text.append(" ".join(lines))
text = re.sub(r"\s+", " ", " ".join(text))
sentences = re.split(r"(?<=[.;:])\s+(?=[A-Z(])", text)

UNITS = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
WORD = re.compile(r"\b(?:(?:%s)(?:-(?:%s))?|%s)\b" % ("|".join(TENS), "|".join(UNITS[:9]), "|".join(UNITS)), re.I)
DIGIT = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
NONE = re.compile(r"\b(?:None of|[Nn]o (?:subjects?|patients?|significant|statistically|clinically|new|deaths?|serious|evidence|apparent|consistent|notable|meaningful|trend|differences?)|There (?:were|was) no)\b")

digits = len(DIGIT.findall(text))
# A number word counts as a RESULT when it counts subjects, events, analytes or deaths.
RESULT_NOUN = re.compile(r"^(?:\S+\s){0,3}?(?:of the \d+ |additional |other |laboratory |serious |adverse |subjects?|patients?|deaths?|analytes?|events?)", re.I)
words_only, words_and_digits, other_words = [], [], []
for s in sentences:
    for m in WORD.finditer(s):
        after = s[m.end():]
        snippet = s[max(0, m.start() - 40): m.end() + 50]
        if re.search(r"at least $", s[:m.start()]):
            other_words.append(snippet)          # "at least one AE" defines a percentage, it is not a count
        elif re.match(r"\s*\(\d", after):
            words_and_digits.append(snippet)
        elif RESULT_NOUN.match(after.strip() + " "):
            words_only.append(snippet)
        else:
            other_words.append(snippet)
none_claims = [s for s in sentences if NONE.search(s) and not DIGIT.search(s)]

def distinct(xs):
    return len({re.sub(r"\W+", " ", x).strip().lower() for x in xs})

out = {"pages": f"{len(PAGES)} narrative pages",
       "numbers_in_digits": digits,   # every digit string: results, but also table/section numbers and dates
       "distinct": {"result_counts_in_words_only": distinct(words_only), "words_with_digits": distinct(words_and_digits),
                    "none_or_no_claims_without_digits": len(set(none_claims))},
       "result_counts_in_words_only": words_only, "words_with_digits": words_and_digits,
       "none_or_no_claims_without_digits": none_claims, "other_number_words": other_words}
json.dump(out, open("s2_results.json", "w"), indent=1)
print("digit strings:", digits, "| distinct:", out["distinct"])
for k in ("result_counts_in_words_only", "words_with_digits", "none_or_no_claims_without_digits", "other_number_words"):
    print(f"\n== {k}: {len(out[k])}")
    for x in out[k]:
        print("  -", x[:170])
