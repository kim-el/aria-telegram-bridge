## Architecture Decisions

This project went through 12+ architecture iterations. Key lessons:

### JSONL over tmux scraping
tmux capture-pane is unreliable: scrollback recycles lines, status bars shift, ANSI codes vary. Claude Code writes structured JSONL session logs — clean text, no scraping, byte-offset tracking works reliably.

### Flash-Pro pipeline over Flash-format bridge
A second Claude call to "reformat" responses destroyed context and added latency. Letting Flash handle chat naturally and spawn Pro on-demand keeps context intact.

### `--continue` over subprocess spawning
Fresh `claude -p` per message costs 20s startup. `--continue` preserves session context across calls. But persistent tmux + JSONL polling is even faster (0s startup) for always-on use.

### Human-like bubbles
15-word max per bubble, 0.5s base + per-char delay + random jitter. Splits on paragraph breaks, caps at 4 bubbles.
