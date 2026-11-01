"""Re-orders search candidates by reading question and passage together with the mxbai-rerank cross-encoder (runs on CPU)."""
import hashlib
from pathlib import Path

MODEL = "mixedbread-ai/mxbai-rerank-base-v1"
VERSION = "1"  # bump when the scoring setup changes (max_length, dtype ...): old cached scores then stop matching
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "rerank"
_model = None


def _key(question, text):
    """Cache key: changes when the model, the setup version, the question or the passage text changes."""
    return hashlib.sha256("\x1f".join([MODEL, VERSION, question, text]).encode("utf-8")).hexdigest()


def _predict(question, texts):
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        import torch
        _model = CrossEncoder(MODEL, device="cpu", max_length=512,
                              model_kwargs={"torch_dtype": torch.float32})  # float16 is ~100x slower on CPU
    return _model.predict([(question, t) for t in texts], batch_size=16).tolist()


def scores(question, texts):
    """One relevance score per passage text, in the same order (higher = better match). Scores are cached on disk."""
    files = [CACHE_DIR / (_key(question, t) + ".txt") for t in texts]
    got = {}
    for i, f in enumerate(files):
        try:
            got[i] = float(f.read_text(encoding="ascii"))
        except (OSError, ValueError):
            pass  # no usable cache entry: score it below
    miss = [i for i in range(len(texts)) if i not in got]
    if miss:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for i, s in zip(miss, _predict(question, [texts[i] for i in miss])):
            got[i] = s
            files[i].write_text(repr(s), encoding="ascii")  # repr of a float reads back exactly
    return [got[i] for i in range(len(texts))]


def rerank(question, candidates, k=5):
    """candidates = list of Quotes. Returns the best k as Quotes whose score is the reranker score, best first."""
    if not candidates:
        return []
    got = scores(question, [c.text for c in candidates])
    order = sorted(range(len(candidates)), key=lambda i: (-got[i], candidates[i].chunk_id))[:k]
    return [type(candidates[i])(candidates[i].chunk_id, candidates[i].doc_id, candidates[i].page,
                                candidates[i].table_id, candidates[i].text, got[i]) for i in order]
