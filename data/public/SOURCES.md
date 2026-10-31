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
| ich/M4Q_R1.pdf | https://database.ich.org/sites/default/files/M4Q_R1_Guideline.pdf | 2026-10-31 | c3edcf44203ad72b9eb0e01bfa3cfbcb6ab4ad6e78304bc985e3a1a03bedff58 |
| ich/Q1A_R2.pdf | https://database.ich.org/sites/default/files/Q1A%28R2%29%20Guideline.pdf | 2026-10-31 | bc7124e1e7c6bde5a460b5f7a00f0e084181f2cde4902a602192f3e656e1246f |
| ich/Q1E.pdf | https://database.ich.org/sites/default/files/Q1E%20Guideline.pdf | 2026-10-31 | 5926a3a462dadfa38d47efe902d749302697a9a3f1f613d0d8d172bb3d62960d |
| ich/Q3B_R2.pdf | https://database.ich.org/sites/default/files/Q3B%28R2%29%20Guideline.pdf | 2026-10-31 | d84ddb26cc34e3d2c380abe12e9269d4bd8840ab1498144146464e484c755a20 |
| ich/Q6A.pdf | https://database.ich.org/sites/default/files/Q6A_Guideline.pdf | 2026-10-31 | 02aeb1c7c2eb499044d584438c001be194f0db02d73ad786f30d7a719b629080 |

FDA Chemistry Review, NDA 215341 (Kerendia, finerenone), original approval 2021. 36 pages, all with a text layer.

DailyMed SPL XML for Kerendia, set id fc726765-5d5a-4d6e-b037-b847bda9fb7c. v1 = first version, effective 2021-07-09 (published 2021-07-14), strengths 10 and 20 mg. v12 = effective 2025-07-29 (published 2025-07-31), strengths 10, 20 and 40 mg. Note: the `services/v2/spls/<setid>.xml?version=N` URL ignores `version` and always returns the newest label, so the zip URL above is used. Only the XML was kept from each zip (images dropped).

NIST StRD univariate reference datasets (public domain, US government). Certified mean and SD are read from each file header by tests/test_stats_basic.py.

NIST StRD linear regression dataset Norris (36 points, ozone monitor calibration). Certified B0, B1 and residual SD are read from the file header by tests/test_r_crosscheck.py. Data columns are y then x.

ICH guidelines (database.ich.org, Step 4): M4Q(R1) 12 Sep 2002 (24 pages); Q1A(R2) 6 Feb 2003 (24); Q1E 6 Feb 2003 (19); Q3B(R2) 2 Jun 2006 (16); Q6A 6 Oct 1999 (35). Used only as quotable text chunks (table kb_chunks), never as facts. Q3B(R2) Attachment 1 threshold tables are on page 11; Q1E has no real table (its decision tree on page 12 is a flow chart).
