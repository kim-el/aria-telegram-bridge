# ARIA — Claude Code Telegram Bridge

A Telegram bot powered by a two-model Claude Code pipeline: Flash handles chat (fast, warm, human-like), Pro handles heavy work (bash, GPU checks, vastai). 

```
You (Telegram)
     │
     ▼
┌─────────────┐
│ Python Bridge│  ~100 lines
│              │  tmux → aria-flash → reads JSONL
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────┐
│     aria-flash (persistent)      │  deepseek-v4-flash
│  - chats like a friend           │  instant replies
│  - 2-4 short bubbles             │  warm, casual tone
│  - spawns Pro when needed        │
│    claude -p "q" --model pro     │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│     aria-pro (on-demand)         │  deepseek-v4-pro
│  - heavy analysis                │  ~20s per query
│  - bash, files, vastai, GPU      │  full tool access
└──────────────────────────────────┘
```

Flash is the human interface. Pro is the backend worker. If Pro gets stuck, Flash retries or adapts.

## Setup

```bash
git clone https://github.com/kim-el/aria-telegram-bridge
cd aria-telegram-bridge
pip install python-telegram-bot

# Set env vars
export BOT_TOKEN="your-telegram-bot-token"
export OWNER_ID="your-telegram-chat-id"
export ANTHROPIC_API_KEY="sk-your-key"
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export CLAUDE_CODE_SIMPLE=1

# Start bridge (auto-creates aria-flash tmux session)
python3 telegram_claude_bridge.py

# Optional: create persistent Pro for heavy work
tmux new-session -d -s aria-pro 'claude --model deepseek-v4-pro --permission-mode auto'
```

Commands: `/start` `/status`. Everything else goes to Flash.
