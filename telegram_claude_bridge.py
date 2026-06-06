import os, subprocess, asyncio, json, threading, tempfile, glob, time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
SESSION = "aria-flash"
os.environ["ANTHROPIC_API_KEY"] = os.environ["DEEPSEEK_KEY"] = "sk-5b400a3177cb44089b29915c231edb5f"
os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
os.environ["ANTHROPIC_MODEL"] = "deepseek-v4-flash"
os.environ["CLAUDE_CODE_SIMPLE"] = "1"
lock = threading.Lock()

LOG_DIR = "/root/.claude/projects/-root"

def find_flash_log():
    """Find the JSONL session log for aria-flash."""
    for f in sorted(glob.glob(f"{LOG_DIR}/*.jsonl"), key=os.path.getmtime, reverse=True):
        try:
            with open(f) as fh:
                for _ in range(5):
                    line = fh.readline()
                    if not line: break
                    if 'aria-flash' in line.lower() or 'aria_flash' in line.lower():
                        return f
        except: pass
    return None

def read_reply(logfile, after_bytes):
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

def send_tmux(msg):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(msg); f.flush()
        subprocess.run(f"tmux load-buffer -t {SESSION} {f.name}", shell=True)
        subprocess.run(f"tmux paste-buffer -t {SESSION} -d", shell=True)
        subprocess.run(f"tmux send-keys -t {SESSION} Enter", shell=True)
    try: os.unlink(f.name)
    except: pass

def ensure_session():
    if subprocess.run(f"tmux has-session -t {SESSION}", shell=True).returncode != 0:
        subprocess.run(f"tmux new-session -d -s {SESSION} \"source /root/.aria_env && ANTHROPIC_MODEL=deepseek-v4-flash claude --name aria-flash --permission-mode auto 2>&1\"", shell=True)
        time.sleep(5)
        subprocess.run(f"tmux send-keys -t {SESSION} Enter", shell=True)
        time.sleep(1)
        # Inject prompt
        prompt = "You are ARIA, a warm Telegram assistant. Reply in 2-4 short casual messages. Chat like a friend first, then do work in background. For heavy tasks: write question to /tmp/q.txt and send to aria-pro via tmux. Never say as an AI."
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt); f.flush()
            subprocess.run(f"tmux load-buffer -t {SESSION} {f.name}", shell=True)
            subprocess.run(f"tmux paste-buffer -t {SESSION} -d", shell=True)
            subprocess.run(f"tmux send-keys -t {SESSION} Enter", shell=True)
        try: os.unlink(f.name)
        except: pass
        time.sleep(3)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.text
    if not lock.acquire(blocking=False):
        await update.message.reply_text("one sec...")
        return
    try:
        await update.message.chat.send_action("typing")
        ensure_session()

        log = find_flash_log() or os.environ.get("ARIA_FLASH_LOG_PATH", "")
        start_bytes = os.path.getsize(log) if log and os.path.exists(log) else 0
        send_tmux(msg)

        # Poll JSONL for new assistant text
        reply = ""
        for _ in range(300):
            await asyncio.sleep(0.3)
            reply, _ = read_reply(log, start_bytes)
            if reply: break

        if not reply:
            await update.message.reply_text("hmm, nothing came back")
            return

        # Permission question?
        if any(w in reply.lower() for w in ['do you want to proceed','requires confirmation','auto mode classifier']):
            await update.message.reply_text(reply[:4000] + '\n\nReply 1=yes 2=yes,always 3=no')
            return

        # Send as bubbles
        bubbles = [b.strip() for b in reply.split('\n\n') if b.strip()]
        if len(bubbles) <= 1:
            bubbles = [b.strip() for b in reply.split('\n') if b.strip()]
        for b in bubbles[:4]:
            await update.message.reply_text(b[:4000])
            if len(bubbles) > 1:
                await asyncio.sleep(0.4)

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
    print("ARIA: JSONL mode")
    app.run_polling()

if __name__ == "__main__":
    main()
