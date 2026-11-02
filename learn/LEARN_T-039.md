# LEARN T-039 - One door to the model, and code that checks its answers
Built: one model client that talks to Ollama (laptop), an OpenAI-style server (Kaggle) or a fake model, plus a loop that asks, checks, and retries up to 4 times. A second tool asks the model for JSON and checks it.
Why this way: one small client with three plug-in backends, so the loop never cares which model is behind it. Not chosen: a model library (LangChain etc.), because it adds a dependency and hides the exact request we need to inspect.
New words: structured output = the model must answer in a fixed JSON shape; schema = the written description of that shape; verbatim = word for word as in the source.
Look at: ectd_engine/writer/structured.py - a value is accepted only if the shape fits AND it appears in the source text.
Try it: python tools/writer_run.py --backend mock - last line says "8/8 accepted".
Remember: the model proposes, the code decides.
