"""Re-derive CSR headline numbers from SDTM, compare with ADSL and with a second
public ADaM package. Data: CDISC SDTM/ADaM Pilot (cdisc-org/sdtm-adam-pilot-project)
and R Consortium Pilot 1 (RConsortium/submissions-pilot1-to-fda). Read-only: no data altered."""
import json, os, sys
import numpy as np, pandas as pd
# folder with: cdisc_adsl.xpt (CDISC pilot ADaM), rc_adsl.xpt (R Consortium pilot 1 ADaM),
# sdtm_dm.xpt, sdtm_ds.xpt, sdtm_sv.xpt (CDISC pilot SDTM)
D = os.path.join(sys.argv[1] if len(sys.argv) > 1 else "data", "")
def rd(f):
    d = pd.read_sas(D + f, format="xport", encoding="latin1")
    for c in d.columns:
        if not pd.api.types.is_numeric_dtype(d[c]):
            d[c] = d[c].astype(object).map(lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip())
    return d
a, rc, dm, ds, sv = rd("cdisc_adsl.xpt"), rd("rc_adsl.xpt"), rd("sdtm_dm.xpt"), rd("sdtm_ds.xpt"), rd("sdtm_sv.xpt")
out = {}
# 1. Are the two ADaM packages independent?
A, R = a.set_index("USUBJID"), rc.set_index("USUBJID").loc[a.set_index("USUBJID").index]
common = [c for c in A.columns if c in R.columns]
ndiff = 0
for c in common:
    x, y = A[c], R[c]
    if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
        ndiff += int((~np.isclose(x.values, y.values, atol=1e-6, equal_nan=True)).sum())
    else:
        ndiff += int((x.astype(str) != y.astype(str)).sum())
out["adsl_cdisc_vs_rconsortium"] = {"subjects": len(A), "shared_variables": len(common), "differing_values": ndiff}
# 2. Re-derive from SDTM
order = ["Placebo", "Xanomeline Low Dose", "Xanomeline High Dose"]
rand = dm[dm.ARM != "Screen Failure"]; arm = dict(zip(rand.USUBJID, rand.ARM))
def by_arm(ids):
    s = pd.Series([arm[i] for i in set(ids) if i in arm]).value_counts()
    return [int(s.get(o, 0)) for o in order]
sdtm = {
    "randomised": by_arm(rand.USUBJID),
    "completed week 24 visit": by_arm(sv[sv.VISITNUM == 12].USUBJID),
    "completed study": by_arm(ds[(ds.DSCAT == "DISPOSITION EVENT") & (ds.DSDECOD == "COMPLETED")].USUBJID),
    "deaths": by_arm(ds[ds.DSDECOD == "DEATH"].USUBJID),
    "male / female": [int((rand.SEX == "M").sum()), int((rand.SEX == "F").sum())],
    "age mean (SD)": [round(rand.AGE.mean(), 1), round(rand.AGE.std(), 2)],
    "white (all) / white not Hispanic": [int((rand.RACE == "WHITE").sum()),
                                          int(((rand.RACE == "WHITE") & (rand.ETHNIC == "NOT HISPANIC OR LATINO")).sum())],
}
csr = {  # as printed in the 2006 CSR text (synopsis and section 10/11)
    "randomised": [86, 84, 84], "completed week 24 visit": [60, 28, 30], "completed study": [58, 25, 27],
    "deaths": "3 in total", "male / female": [111, 143], "age mean (SD)": [75.1, 8.25],
    "white (all) / white not Hispanic": "218 (86%) Caucasian; 12 (5%) Hispanic",
}
out["sdtm_rederived"] = sdtm; out["csr_text"] = csr

# 3. Can the SDTM route catch a wrong ADaM flag? Subject by subject, then with planted errors.
#    Flags are changed in an in-memory copy only; no file is written or altered.
A2 = a.set_index("USUBJID")
ids = set(rand.USUBJID)
sdtm_sets = {
    "COMP24FL (completed Week 24)": set(sv[sv.VISITNUM == 12].USUBJID) & ids,
    "DCDECOD = COMPLETED (completed study)": set(ds[(ds.DSCAT == "DISPOSITION EVENT") & (ds.DSDECOD == "COMPLETED")].USUBJID) & ids,
    "DTHFL (died)": set(ds[ds.DSDECOD == "DEATH"].USUBJID) & ids,
}
adam_sets = {
    "COMP24FL (completed Week 24)": set(A2.index[A2.COMP24FL == "Y"]),
    "DCDECOD = COMPLETED (completed study)": set(A2.index[A2.DCDECOD == "COMPLETED"]),
    "DTHFL (died)": set(A2.index[A2.DTHFL == "Y"]),
}
out["subject_level_match"] = {k: sdtm_sets[k] == adam_sets[k] for k in sdtm_sets}
out["week24_completers_all_in_efficacy_population"] = bool((A2.loc[list(adam_sets["COMP24FL (completed Week 24)"]), "EFFFL"] == "Y").all())

def arm_counts(sset):
    return [sum(1 for i in sset if arm[i] == o) for o in order]

rng = np.random.default_rng(7)
planted = {"single flag flipped": [0, 0, 0], "two flags swapped within an arm": [0, 0, 0]}
# columns: [errors planted, caught by comparing per-arm counts with SDTM, caught subject by subject]
for k, flags in adam_sets.items():
    for sid in sorted(ids):                       # flip each subject's flag once
        wrong = flags ^ {sid}
        planted["single flag flipped"][0] += 1
        planted["single flag flipped"][1] += arm_counts(wrong) != arm_counts(sdtm_sets[k])
        planted["single flag flipped"][2] += wrong != sdtm_sets[k]
    for _ in range(200):                          # one Y->N and one N->Y in the same arm: counts unchanged
        o = rng.choice(order)
        yes = sorted(i for i in flags if arm[i] == o); no = sorted(i for i in ids - flags if arm[i] == o)
        if not yes or not no:
            continue
        wrong = (flags - {rng.choice(yes)}) | {rng.choice(no)}
        planted["two flags swapped within an arm"][0] += 1
        planted["two flags swapped within an arm"][1] += arm_counts(wrong) != arm_counts(sdtm_sets[k])
        planted["two flags swapped within an arm"][2] += wrong != sdtm_sets[k]
out["planted_flag_errors"] = {k: {"planted": v[0], "caught_by_counts": v[1], "caught_subject_by_subject": v[2]}
                              for k, v in planted.items()}
out["note"] = ("Re-counting the same ADaM flags always agrees with tables made from them, so it catches none of these "
               "by definition. Week-24 completers: SV visit 12; all are also in the efficacy population (EFFFL=Y), "
               "which is the CSR's definition. SDTM is itself built by the sponsor, so an error made when collecting "
               "or mapping the data is shared by both routes.")
json.dump(out, open("s3_results.json", "w"), indent=1)
print(json.dumps(out, indent=1))
