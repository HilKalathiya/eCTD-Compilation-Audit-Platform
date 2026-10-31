"""Cuts the ICH guideline PDFs into small searchable chunks that remember document, version, page and table id."""
import hashlib
import re
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[2]
ICH_DIR = ROOT / "data" / "public" / "ich"
DOCS = {  # doc_id -> PDF file name
    "M4Q_R1": "M4Q_R1.pdf",
    "Q1A_R2": "Q1A_R2.pdf",
    "Q1E": "Q1E.pdf",
    "Q3B_R2": "Q3B_R2.pdf",
    "Q6A": "Q6A.pdf",
}
TEXT_TARGET = 800     # characters per text chunk (about)
TABLE_MAX = 1500      # a table bigger than this is cut into row-groups (never inside a row)
HEAD_ZONE, FOOT_ZONE = 55, 45   # page header / footer bands (points) that carry no content
CELL_GAP = 20         # horizontal gap (points) that separates two table cells
DRAW_MAX = 20         # a page with more vector lines than this and no ruled table is treated as a figure
ROW_TOL = 5           # words whose centres are this close vertically are one row
MONTHS = {m: i for i, m in enumerate(
    "January February March April May June July August September October November December".split(), 1)}
VERSION_RE = re.compile(r"Current Step 4 version dated (\d{1,2}) (\w+) (\d{4})")
HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+\S")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def doc_version(doc):
    """Read 'Current Step 4 version dated <d> <month> <yyyy>' from page 1 -> 'Step 4 yyyy-mm-dd'."""
    m = VERSION_RE.search(" ".join(doc[0].get_text().split()))
    if not m:
        raise ValueError("no 'Current Step 4 version dated ...' line on page 1")
    return f"Step 4 {int(m[3]):04d}-{MONTHS[m[2]]:02d}-{int(m[1]):02d}"


def make_chunk(doc_id, version, page, text, heading, chunk_id, table_id=None):
    text = text.strip()
    return {"chunk_id": f"{doc_id}:{chunk_id}", "doc_id": doc_id, "doc_version": version, "page": page,
            "table_id": table_id, "heading_path": heading, "text": text, "sha256": sha(text)}


def _inside(box, outer):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return outer[0] - 1 <= cx <= outer[2] + 1 and outer[1] - 1 <= cy <= outer[3] + 1


SYMBOLS = {"": "≤", "": "≥", "": "±", "": "°", "": "•",
           "": " ", "": "×", "": "→"}  # Symbol-font characters the PDF stores as private-use codes


def fix_symbols(text):
    return "".join(SYMBOLS.get(ch, ch) for ch in text)


def _clean(cell):
    return " ".join(fix_symbols(cell or "").split())


def _good_table(rows):
    """A real table: at least 2 rows, half the cells filled, and mostly words (not axis numbers or page dots)."""
    cells = [c for r in rows for c in r]
    filled = [c for c in cells if c]
    if len(rows) < 2 or len(filled) * 2 < len(cells):
        return False
    letters = [c for c in filled if re.search(r"[A-Za-z]{2}", c)]
    if len(letters) * 3 < len(filled):
        return False
    if all(re.fullmatch(r"[\d.]+", r[0]) for r in rows if r[0]) and any(r[0] for r in rows):
        return False  # footnote list: '1 | text'
    if sum(1 for r in rows if re.search(r"\.{4,}\s*\d*$", r[-1])) * 2 > len(rows):
        return False  # table of contents
    return True


def ruled_tables(page):
    """Tables PyMuPDF finds from ruling lines -> [(bbox, rows)]."""
    out = []
    for t in page.find_tables().tables:
        rows = [[_clean(c) for c in r] for r in t.extract()]
        if _good_table(rows):
            out.append((tuple(t.bbox), rows, ""))
    return out


def borderless_tables(page, skip_boxes):
    """Tables without ruling lines: runs of text rows that each hold 2+ cells separated by wide gaps."""
    words = [w for w in page.get_text("words")
             if HEAD_ZONE < (w[1] + w[3]) / 2 < page.rect.height - FOOT_ZONE
             and not any(_inside(w[:4], b) for b in skip_boxes)]
    words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines, yc = [], None
    for w in words:
        y = (w[1] + w[3]) / 2
        if yc is None or abs(y - yc) > ROW_TOL:
            lines.append([])
            yc = y
        lines[-1].append(w)
    parsed = []  # per line: (cells, bbox)
    for ws in lines:
        ws.sort(key=lambda w: w[0])
        cells, cur = [], [ws[0]]
        for prev, w in zip(ws, ws[1:]):
            if w[0] - prev[2] > CELL_GAP:
                cells.append(cur)
                cur = []
            cur.append(w)
        cells.append(cur)
        parsed.append(([_clean(" ".join(w[4] for w in c)) for c in cells],
                       (min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws))))
    runs, run = [], []
    for i, (cells, box) in enumerate(parsed):
        if len(cells) >= 2:
            if not run and i and len(parsed[i - 1][0]) == 1 and len(parsed[i - 1][0][0]) < 60 \
                    and not parsed[i - 1][0][0].endswith("."):
                run.append(parsed[i - 1])  # one-cell caption right above, e.g. 'Reporting Thresholds'
            run.append((cells, box))
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    out = []
    for run in runs:
        title = run.pop(0)[0][0] if len(run[0][0]) == 1 else ""
        if len(run) < 3:
            continue
        counts = [len(c) for c, _ in run]
        if counts.count(max(set(counts), key=counts.count)) * 5 < len(run) * 3:
            continue  # cell count jumps around: a flow chart or indented prose, not a table
        width = max(counts)
        rows = [c + [""] * (width - len(c)) for c, _ in run]
        bbox = (min(b[0] for _, b in run), min(b[1] for _, b in run), max(b[2] for _, b in run), max(b[3] for _, b in run))
        if _good_table(rows):
            out.append((bbox, rows, title))
    return out


def table_groups(rows, title=""):
    """Text of one table as one or more row-groups; a table over TABLE_MAX characters is cut between rows."""
    lines = [" | ".join(r) for r in rows]
    groups, cur, size = [], [], 0
    for line in lines:
        if cur and size + len(line) > TABLE_MAX:
            groups.append(cur)
            cur, size = [lines[0]], len(lines[0])  # header row repeated in each group
        cur.append(line)
        size += len(line) + 1
    groups.append(cur)
    return ["\n".join(([title] if title else []) + g) for g in groups]


def _split_long(text):
    """Cut a very long paragraph at sentence ends into pieces of about TEXT_TARGET characters."""
    pieces, cur = [], ""
    for s in re.split(r"(?<=[.;:])\s+", text):
        if cur and len(cur) + len(s) > TEXT_TARGET:
            pieces.append(cur)
            cur = ""
        cur = f"{cur} {s}".strip()
    return pieces + [cur]


def page_blocks(page, table_boxes):
    """Paragraphs of one page as (y, text, is_heading), skipping header/footer bands and table areas.
    A run of bold lines is a heading of its own; the other lines of the block stay a paragraph."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0 or not HEAD_ZONE < (b["bbox"][1] + b["bbox"][3]) / 2 < page.rect.height - FOOT_ZONE:
            continue
        if any(_inside(b["bbox"], t) for t in table_boxes):
            continue
        lines = [(fix_symbols("".join(s["text"] for s in l["spans"]).strip()), all(s["flags"] & 16 for s in l["spans"]), l["bbox"][1])
                 for l in b["lines"] if l["spans"]]
        group = []  # consecutive lines of the same kind (bold or not)
        for t, bold, y in [x for x in lines if x[0]] + [("", None, 0)]:
            if group and bold != group[0][1]:
                text = re.sub(r"\s+", " ", " ".join(g[0] for g in group))
                head = group[0][1] and len(text) < 110 and "...." not in text and (
                    bool(HEADING_RE.match(text)) or text.isupper() or text.startswith("Attachment"))
                out.append((group[0][2], text, bool(head)))
                group = []
            if bold is not None:
                group.append((t, bold, y))
    return sorted(out)


def chunk_document(doc_id, path=None):
    """All chunks of one guideline, in reading order."""
    doc = fitz.open(path or ICH_DIR / DOCS[doc_id])
    version = doc_version(doc)
    chunks, path_stack = [], []
    for page_no, page in enumerate(doc, start=1):
        tables = ruled_tables(page)
        if tables or len(page.get_drawings()) < DRAW_MAX:  # many lines but no ruled table = a flow chart, not a table
            tables += borderless_tables(page, [t[0] for t in tables])
        tables.sort(key=lambda t: t[0][1])
        blocks = page_blocks(page, [t[0] for t in tables])
        events = [(y, "text", (t, h)) for y, t, h in blocks]
        events += [(bbox[1], "table", (n, rows, title)) for n, (bbox, rows, title) in enumerate(tables, start=1)]
        events.sort(key=lambda e: e[0])
        pending, size, count = [], 0, 0

        def flush():
            nonlocal pending, size, count
            if pending:
                count += 1
                chunks.append(make_chunk(doc_id, version, page_no, "\n".join(pending), " > ".join(path_stack),
                                         f"p{page_no}-c{count}"))
            pending, size = [], 0

        for _, kind, data in events:
            if kind == "table":
                flush()
                n, rows, title = data
                groups = table_groups(rows, title)
                for g, text in enumerate(groups, start=1):
                    tid = f"p{page_no}-t{n}"
                    chunks.append(make_chunk(doc_id, version, page_no, text, " > ".join(path_stack),
                                             tid if len(groups) == 1 else f"{tid}.g{g}", tid))
                continue
            text, is_head = data
            if is_head:
                flush()
                m = HEADING_RE.match(text)
                level = len(m[1].split(".")) if m else 1
                del path_stack[level - 1:]
                path_stack.append(text)
                continue
            for piece in (_split_long(text) if len(text) > 2 * TEXT_TARGET else [text]):
                if pending and size + len(piece) > TEXT_TARGET:
                    flush()
                pending.append(piece)
                size += len(piece)
        flush()
    return chunks


def chunk_all():
    return {d: chunk_document(d) for d in DOCS}
