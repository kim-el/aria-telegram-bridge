import os, subprocess, asyncio, json, threading, tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
SESSION = "aria-claude"
os.environ["ANTHROPIC_API_KEY"] = os.environ["DEEPSEEK_KEY"] = "sk-5b400a3177cb44089b29915c231edb5f"
os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
FLASH = {**os.environ, "ANTHROPIC_MODEL": "deepseek-v4-flash"}
PRO = {**os.environ, "ANTHROPIC_MODEL": "deepseek-v4-pro", "ANTHROPIC_SMALL_FAST_MODEL": "deepseek-v4-flash"}
lock = threading.Lock()

def claude_flash(prompt, max_turns=1, timeout=30):
    r = subprocess.run(
        ["claude", "-p", prompt, "--permission-mode", "auto",
         "--max-turns", str(max_turns), "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout,
        cwd="/root", env={**os.environ, **FLASH, "HOME": "/root"}
    )
    return (r.stdout + r.stderr).strip()

def send_tmux(msg):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(msg); f.flush()
        subprocess.run(f'tmux load-buffer -t {SESSION} {f.name}', shell=True)
        subprocess.run(f'tmux paste-buffer -t {SESSION} -d', shell=True)
        subprocess.run(f'tmux send-keys -t {SESSION} Enter', shell=True)
    try: os.unlink(f.name)
    except: pass

def read_log(logfile, after_bytes):
    if not logfile or not os.path.exists(logfile): return "", after_bytes
    texts = []
    with open(logfile) as fh:
        fh.seek(after_bytes)
        for line in fh:
            try:
                d = json.loads(line.strip())
                msg = d.get("message", {})
                if msg.get("role") != "assistant": continue
                for block in msg.get("content", []):
                    if block.get("text"):
                        texts.append(block["text"])
            except: pass
    return '\n'.join(texts), os.path.getsize(logfile)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.text
    if not lock.acquire(blocking=False):
        await update.message.reply_text("one sec...")
        return
    try:
        # ── Pipeline: Flash ack → persistent Pro (tmux) → Flash format → bubbles ──

        # Layer 1: Flash instant ack (stateless, fast)
        ack = claude_flash(
            f"User said: '{msg}'. Reply with a short casual acknowledgment. Under 5 words. Be natural. Just the phrase, nothing else.",
            max_turns=1, timeout=10
        )
        if ack:
            await update.message.reply_text(ack.strip()[:200])

        # Layer 2: Send to persistent aria-claude (maintains context, uses Pro)
        log = os.environ.get("ARIA_LOG_PATH", "")
        start_bytes = os.path.getsize(log) if os.path.exists(log) else 0
        send_tmux(msg)

        # Wait for response via JSONL
        await update.message.chat.send_action("typing")
        pro_reply = ""
        for _ in range(300):
            await asyncio.sleep(0.3)
            pro_reply, _ = read_log(log, start_bytes)
            if pro_reply:
                if any(w in pro_reply.lower() for w in ['do you want to proceed','requires confirmation','auto mode classifier']):
                    await update.message.reply_text(pro_reply[:4000] + '\n\nReply 1=yes 2=yes,always 3=no')
                    return
                break

        if not pro_reply:
            await update.message.reply_text("hmm, nothing came back. try again?")
            return

        # Layer 3: Flash reformats into chat bubbles (stateless, fast)
        formatted = claude_flash(
            f"Rewrite as 2-4 casual text messages. One sentence per line. No markdown, no emojis. Keep key facts. Sound like a friend:\n\n{pro_reply}",
            max_turns=1, timeout=15
        )
        text = formatted if formatted else pro_reply

        # Send as bubbles
        bubbles = [b.strip() for b in text.split('\n') if b.strip()][:4]
        for i, b in enumerate(bubbles):
            if i > 0:
                delay = 0.3 + len(b) * 0.02 + (hash(b[:10]) % 8) * 0.03
                await asyncio.sleep(min(delay, 5.0))
            await update.message.reply_text(b[:4000])

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:500]}")
    finally:
        lock.release()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    await update.message.reply_text("ARIA ready. /status")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    gpu = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used --format=csv,noheader", shell=True, capture_output=True, text=True).stdout.strip()
    await update.message.reply_text(f"GPU: {gpu}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ARIA: Flash→Pro→Flash pipeline")
    app.run_polling()

if __name__ == "__main__":
    main()
