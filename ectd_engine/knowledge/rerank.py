"""Re-orders search candidates by reading question and passage together with the mxbai-rerank cross-encoder (runs on CPU)."""
MODEL = "mixedbread-ai/mxbai-rerank-base-v1"
_model = None


def scores(question, texts):
    """One relevance score per passage text, in the same order (higher = better match). Model loads once, then stays cached."""
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        import torch
        _model = CrossEncoder(MODEL, device="cpu", max_length=512,
                              model_kwargs={"torch_dtype": torch.float32})  # float16 is ~100x slower on CPU
    return _model.predict([(question, t) for t in texts], batch_size=16).tolist()


def rerank(question, candidates, k=5):
    """candidates = list of Quotes. Returns the best k as Quotes whose score is the reranker score, best first."""
    if not candidates:
        return []
    got = scores(question, [c.text for c in candidates])
    order = sorted(range(len(candidates)), key=lambda i: (-got[i], candidates[i].chunk_id))[:k]
    return [type(candidates[i])(candidates[i].chunk_id, candidates[i].doc_id, candidates[i].page,
                                candidates[i].table_id, candidates[i].text, got[i]) for i in order]
