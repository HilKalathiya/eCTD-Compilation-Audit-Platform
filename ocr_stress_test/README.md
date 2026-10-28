# OCR + VLM cross-check stress test

Reproduces the flaw in the first OCR + VLM cross-check design and measures the fix,
on real batch values from the Lek/Sandoz dataset (Zagar & Mihelic, Scientific Data 2022,
CC BY 4.0, https://www.nature.com/articles/s41597-022-01203-x).

## What it does
1. Prints 40 certificate-style tables (10 real batches x 6 results each) from `Laboratory.csv`.
2. Degrades each table to 4 scan qualities (clean 300 dpi, good scan 200 dpi, poor scan 150 dpi,
   fax/photocopy 150 dpi black and white): 9,600 values in total. See `scan_levels_real.png`.
3. Reads them with two OCR engines from different families: Tesseract 5 (page OCR) and
   PP-OCR via RapidOCR (cell crops, standing in for the VLM's own visual read).
4. Scores the NAIVE design (VLM sees OCR words and points to one; accept if texts match),
   sweeping how often the VLM repeats the OCR text (0-100%) and injecting 2% row slips.
5. Scores the FIXED design: deskew + grid binding + header check, two blind reads,
   column-aware typed parsing, column rules, zoom re-read on disagreement, else a person.

## Results (from summary.json)
Fixed design: 0 silently wrong values out of 9,600; sent to a person 0% (clean, good scan),
6.0% (poor scan), 2.1% (fax). See analysis2.txt for every count.

## Run
    pip install rapidocr_onnxruntime opencv-python pytesseract pandas   # plus the tesseract binary
    python run.py path/to/Laboratory.csv 40 results.json   # ~25 min on 2 CPU cores
    python analyze.py results.json                          # writes summary.json
    python make_doc.py                                      # prints the results table

Note: the CSV is semicolon-separated; the dataset spells one column `resodual_solvent`.
No VLM is called. Measure your own VLM's copy rate with seeded tests before trusting agreement.
