import os, subprocess, asyncio, json, threading, tempfile, re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
SESSION = "aria-claude"
os.environ["ANTHROPIC_API_KEY"] = "sk-5b400a3177cb44089b29915c231edb5f"
os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
os.environ["CLAUDE_CODE_SIMPLE"] = "1"
lock = threading.Lock()

def send(msg):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(msg); f.flush()
        subprocess.run(f'tmux load-buffer -t {SESSION} {f.name}', shell=True)
        subprocess.run(f'tmux paste-buffer -t {SESSION} -d', shell=True)
        subprocess.run(f'tmux send-keys -t {SESSION} Enter', shell=True)
    try: os.unlink(f.name)
    except: pass

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

def split_human(text):
    """Split into short human-like messages by sentence boundaries."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    result = []
    for p in parts:
        p = p.strip()
        if not p: continue
        # Further split on commas for long parts
        if len(p) > 300:
            sub = re.split(r'(?<=,)\s+', p)
            result.extend([s.strip() for s in sub if s.strip()])
        else:
            result.append(p)
    # Hard cap at 4000
    final = []
    for m in result:
        while len(m) > 4000:
            final.append(m[:3900] + "...")
            m = m[3900:]
        final.append(m)
    return final

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.text
    if not lock.acquire(blocking=False):
        await update.message.reply_text("Busy.")
        return
    try:
        # Instant ack so user knows we'''re on it
        await update.message.reply_text('on it 👀')

        log = os.environ.get("ARIA_LOG_PATH", "")
        start_bytes = os.path.getsize(log) if os.path.exists(log) else 0
        send(msg)

        reply = ""
        for _ in range(300):
            await asyncio.sleep(0.3)
            reply, _ = read_reply(log, start_bytes)
            if reply:
                # If Claude is asking a permission question, present options clearly
                if any(w in reply.lower() for w in ['do you want to proceed','requires confirmation','auto mode classifier']):
                    reply += '

Reply: 1 (yes) / 2 (yes, always) / 3 (no)'
                break
            # Timeout after 30s without reply - Claude might be waiting on user
            if _ > 100 and not reply:
                reply = 'Claude is waiting for your response. Check tmux aria-claude.'
                break

        if reply:
            chunks = split_human(reply)
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await update.message.chat.send_action("typing")
                    delay = 0.4 + len(chunk) * 0.04 + (hash(chunk[:10]) % 10) * 0.05
                    await asyncio.sleep(min(delay, 8.0))
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text("(no response)")
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
    print("ARIA ready")
    app.run_polling()

if __name__ == "__main__":
    main()
