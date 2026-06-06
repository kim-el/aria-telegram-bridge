# ARIA — Claude Code Telegram Bridge

A lightweight Python bridge that connects Claude Code to Telegram. Claude runs persistently in tmux on any machine — cloud instance, VPS, or local server. ARIA relays messages between Telegram and Claude, reading responses from Claude's JSONL session log.

## How It Works

```
Telegram → Python bridge → tmux paste-buffer → Claude Code (persistent)
                                                          ↓
Telegram ← split & send ← JSONL session log ← Claude responds
```

- **Claude stays alive** in a tmux session — maintains context across messages
- **Bridge reads JSONL logs** — no terminal scraping, clean structured data
- **Human-like replies** — splits long responses into sentence-by-sentence messages with typing delays

## Setup

### 1. Create Telegram Bot
- Message @BotFather on Telegram
- `/newbot` → choose name → get token

### 2. Any Machine (cloud instance, VPS, or local)
```bash
git clone https://github.com/kim-el/aria-telegram-bridge
cd aria-telegram-bridge

# Install deps
pip install python-telegram-bot

# Set env vars
export BOT_TOKEN="your-telegram-bot-token"
export OWNER_ID="your-telegram-chat-id"
export ANTHROPIC_API_KEY="sk-your-deepseek-key"
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_MODEL="deepseek-v4-pro"
export CLAUDE_CODE_SIMPLE=1

# Start Claude in tmux
tmux new-session -d -s claude 'claude --permission-mode auto'

# Find and save its session log
echo "export ARIA_LOG_PATH=$(ls -t ~/.claude/projects/-root/*.jsonl | head -1)" >> ~/.aria_env

# Start bridge
source ~/.aria_env
python3 telegram_claude_bridge.py
```

### 3. Commands
- `/start` — check ARIA is alive
- `/status` — server stats
- Any message → forwarded to Claude

## Files
- `telegram_claude_bridge.py` — the bridge (~120 lines)
- That's it. No framework, no database, no config files.
