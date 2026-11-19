"""Test helper: starts importing torch and sentence_transformers (about 25 s) in a background thread, so the import overlaps with tests that wait on the databases."""
import threading

_thread = None


def _import_heavy_modules():
    try:
        import sentence_transformers  # noqa: F401
        import torch  # noqa: F401
    except Exception:  # a missing package must show up in the test that needs it, not here
        pass


def start():
    """Idempotent. The tests that need the modules simply find them already imported (or wait on Python's import lock)."""
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_import_heavy_modules, name="warm-models", daemon=True)
        _thread.start()


start()
