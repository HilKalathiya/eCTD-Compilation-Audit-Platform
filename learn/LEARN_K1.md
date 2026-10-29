# LEARN K1 - Read the fuel gauge (context and usage)
Built: A note on what fills Claude Code's working memory (context) right now: 68.8k of 1m tokens (7%) used, 898k free.
Why this way: We measured with /context before cutting anything. We did NOT start deleting plugins blindly, because a cut only pays off on the big items.
Biggest 3 items (tokens, % of 1m):
  1 Messages 26.4k (2.6%) - the chat itself. Shrink: /clear between tasks.
  2 MCP 13.1k (1.3%) = tools 6.6k + server instructions 6.5k; 356 tools loaded on demand (275.5k more, 27.6%, only if fetched). Shrink: /mcp disable servers you never use (Figma, Postman, Eraser, Zoom...).
  3 Skills 9.8k (1.0%) - 436 skills listed. Shrink: disable unused plugins with /plugin (bio-research, zoom, brightdata...).
  Next: system tools 9.2k, system prompt 4k, agents 4k (49), CLAUDE.md 2.1k (0.2%, already small).
/usage numbers: session (5-hour) 33% used, resets 7:09pm; week 57% used, resets Nov 1 5:29am. Session cost $0.62; 86% of input came from cache.
New words: context = what Claude holds in mind this session; MCP server = outside tool connection; token = small chunk of text (~4 letters)
Look at: /context output - the Messages row grows as we chat; the rest is fixed.
Try it: /clear then /context - Messages drops to about 0.
Remember: you can't cut waste you haven't measured.
