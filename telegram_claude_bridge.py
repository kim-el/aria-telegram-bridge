import os, subprocess, asyncio, re, threading, tempfile
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

SYSTEM = """You are ARIA, a Telegram assistant running on a vast.ai GPU server (RTX 3060). You are chatting with Kim.
- Reply in 2-4 short messages. Casual tone, like a friend texting.
- For heavy tasks (check training, GPU, vastai balance): spawn Pro:
  claude -p "question" --model deepseek-v4-pro --permission-mode auto --max-turns 25
- Use bash to check files, GPU stats, training logs.
- Never say "as an AI". You are ARIA."""

def start_session():
    """Ensure aria-flash tmux session exists with system prompt."""
    r = subprocess.run(f"tmux has-session -t {SESSION}", shell=True)
    if r.returncode != 0:
        subprocess.run(f"tmux new-session -d -s {SESSION} 'source /root/.aria_env && ANTHROPIC_MODEL=deepseek-v4-flash claude --permission-mode auto 2>&1'", shell=True)
        import time; time.sleep(5)
        subprocess.run(f"tmux send-keys -t {SESSION} Enter", shell=True)
        time.sleep(1)
        # Inject system prompt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(SYSTEM); f.flush()
            subprocess.run(f"tmux load-buffer -t {SESSION} {f.name}", shell=True)
            subprocess.run(f"tmux paste-buffer -t {SESSION} -d", shell=True)
            subprocess.run(f"tmux send-keys -t {SESSION} Enter", shell=True)
        try: os.unlink(f.name)
        except: pass

def send(msg):
    """Send message to persistent aria-flash."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(msg); f.flush()
        subprocess.run(f"tmux load-buffer -t {SESSION} {f.name}", shell=True)
        subprocess.run(f"tmux paste-buffer -t {SESSION} -d", shell=True)
        subprocess.run(f"tmux send-keys -t {SESSION} Enter", shell=True)
    try: os.unlink(f.name)
    except: pass

def pane(tail=80):
    return subprocess.run(f"tmux capture-pane -t {SESSION} -p -S -{tail}", shell=True, capture_output=True, text=True).stdout

def busy():
    p = subprocess.run(f"tmux capture-pane -t {SESSION} -p -S -3", shell=True, capture_output=True, text=True).stdout
    return any(m in p for m in ["Thinking","Running","Jitterbugging","Dilly-dallying","⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"])

def clean(text):
    out = []
    for line in text.split('\n'):
        line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line).strip()
        if not line: continue
        if re.match(r'^(Thought for|● |✻ |Baked|Cooked|Jitterbugging|Dilly-dallying|❯|▎|Hashing)', line): continue
        if '────────────────' in line or 'esc to interrupt' in line or 'auto mode' in line: continue
        if 'aria-flash' in line and len(line) < 40: continue
        out.append(line)
    return '\n'.join(out)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.text
    if not lock.acquire(blocking=False):
        await update.message.reply_text("one sec...")
        return
    try:
        await update.message.chat.send_action("typing")
        start_session()

        # Instant feedback
        dots = await update.message.reply_text("...")

        before = pane()
        send(msg)

        # Wait for response — tight loop
        last = before; idle = 0
        for _ in range(600):
            await asyncio.sleep(0.2)
            cur = pane()
            if cur == last:
                idle += 1
                if idle >= 4 and not busy(): break
            else:
                idle = 0; last = cur

        after = pane()
        # Diff: only new content
        bl = before.split('\n'); al = after.split('\n')
        new_lines = []
        for i, line in enumerate(al):
            if i >= len(bl) or line != bl[i]:
                new_lines = al[i:]
                break
        reply = clean('\n'.join(new_lines))

        if not reply:
            await update.message.reply_text("...")
            return

        # Bubbles
        bubbles = [b.strip() for b in reply.split('\n\n') if b.strip()]
        if len(bubbles) <= 1:
            bubbles = [b.strip() for b in reply.split('\n') if b.strip()]
        bubbles = bubbles[:4]

        for b in bubbles:
            await update.message.reply_text(b[:4000])
            if len(bubbles) > 1:
                await asyncio.sleep(0.5)

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
    start_session()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ARIA: persistent tmux, 200ms poll")
    app.run_polling()

if __name__ == "__main__":
    main()
