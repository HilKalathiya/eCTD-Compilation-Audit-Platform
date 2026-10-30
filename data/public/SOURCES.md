# Public sources

| File | URL | Downloaded | sha256 |
|---|---|---|---|
| kerendia/215341Orig1s000ChemR.pdf | https://www.accessdata.fda.gov/drugsatfda_docs/nda/2021/215341Orig1s000ChemR.pdf | 2026-10-29 | 6c1c820afd2d4b791d867e2a2b517fe278e19dd41f5b162690224703b7e611b9 |
| kerendia/kerendia_spl_v1.xml | https://dailymed.nlm.nih.gov/dailymed/getFile.cfm?type=zip&setid=fc726765-5d5a-4d6e-b037-b847bda9fb7c&version=1 (XML inside the zip) | 2026-10-30 | b24aa6d311a96111b4fc934f46192e454d2de5c24a7aeede2e3c660af20566f9 |
| kerendia/kerendia_spl_v12.xml | https://dailymed.nlm.nih.gov/dailymed/getFile.cfm?type=zip&setid=fc726765-5d5a-4d6e-b037-b847bda9fb7c&version=12 (XML inside the zip) | 2026-10-30 | d69507e94f309d3128c0ece11f3f707565010d39750f0d5d4ec9676345757ca0 |
| nist/NumAcc1.dat | https://www.itl.nist.gov/div898/strd/univ/data/NumAcc1.dat | 2026-10-30 | ce7c7a0fc6d7cedd0d5e1f9911afb9337544be6836730beb9968ca0a4571d375 |
| nist/NumAcc2.dat | https://www.itl.nist.gov/div898/strd/univ/data/NumAcc2.dat | 2026-10-30 | 5be29522dfbe299541f0ec98ec1c22a51a5587bf06561ba21a92c209fb7ef0f9 |
| nist/NumAcc3.dat | https://www.itl.nist.gov/div898/strd/univ/data/NumAcc3.dat | 2026-10-30 | 66df1b96596735936f37fd889e7c1c6ce998eb2b523bfc46c98ec1737e992aec |
| nist/NumAcc4.dat | https://www.itl.nist.gov/div898/strd/univ/data/NumAcc4.dat | 2026-10-30 | ca310dc767f5130f980f8280bbe69e26ba414a4d85a89fc11b6c767b828e5fe4 |
| nist/Michelso.dat | https://www.itl.nist.gov/div898/strd/univ/data/Michelso.dat | 2026-10-30 | 68cad435641539ca020adafb4c9a6b7fcc4fefe1d6ab8f2af8fb858d4f1b12ab |
| nist/Norris.dat | https://www.itl.nist.gov/div898/strd/lls/data/LINKS/DATA/Norris.dat | 2026-10-30 | 5ab6906c68a9c4b2eb1661c0cd7d2a09f5a469a6d4e05b6b691f190f5f7b944f |

FDA Chemistry Review, NDA 215341 (Kerendia, finerenone), original approval 2021. 36 pages, all with a text layer.

DailyMed SPL XML for Kerendia, set id fc726765-5d5a-4d6e-b037-b847bda9fb7c. v1 = first version, effective 2021-07-09 (published 2021-07-14), strengths 10 and 20 mg. v12 = effective 2025-07-29 (published 2025-07-31), strengths 10, 20 and 40 mg. Note: the `services/v2/spls/<setid>.xml?version=N` URL ignores `version` and always returns the newest label, so the zip URL above is used. Only the XML was kept from each zip (images dropped).

NIST StRD univariate reference datasets (public domain, US government). Certified mean and SD are read from each file header by tests/test_stats_basic.py.

NIST StRD linear regression dataset Norris (36 points, ozone monitor calibration). Certified B0, B1 and residual SD are read from the file header by tests/test_r_crosscheck.py. Data columns are y then x.
