# T-063 double entry: Hil's check vs the public CSV

Hil's values were read from PDF page images and transcribed by the brain, not typed blind.

| hil_check.csv (page, what, value) | Public CSV row (data/stability/finerenone_stability.csv) | Match |
|---|---|---|
| p3, proposed expiry period (months) = 36 | 20-25C CRT, expiry_period_proposed = 36 months, p.3 | yes |
| p5, long-term study duration (months) = 36 | 25C/60%RH and 30C/75%RH, study_duration_demonstrated = 36 months, p.5 | yes |
| p5, accelerated study duration (months) = 6 | 40C/75%RH, study_duration_demonstrated = 6 months, p.5 | yes |
| p3, storage temperature range = 20°C to 25°C | condition "20-25C CRT" on the p.3 expiry row | yes |

Result: 4/4 match. hil_check.csv was not edited.
