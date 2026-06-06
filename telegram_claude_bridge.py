import os, subprocess, asyncio, threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
os.environ["ANTHROPIC_API_KEY"] = os.environ["DEEPSEEK_KEY"] = "sk-5b400a3177cb44089b29915c231edb5f"
os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
os.environ["ANTHROPIC_MODEL"] = "deepseek-v4-flash"
os.environ["CLAUDE_CODE_SIMPLE"] = "1"
lock = threading.Lock()

def ask(prompt, timeout=600):
    """Spawn Claude with persistent session. Returns stdout text."""
    r = subprocess.run(
        ["claude", "-p", prompt,
         "--continue", "--permission-mode", "auto",
         "--max-turns", "25", "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout,
        cwd="/root", env={**os.environ, "HOME": "/root"}
    )
    return (r.stdout + r.stderr).strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.text
    if not lock.acquire(blocking=False):
        await update.message.reply_text("one sec...")
        return
    try:
        await update.message.chat.send_action("typing")
        reply = ask(msg)

        if not reply:
            await update.message.reply_text("hmm, nothing. try again?")
            return

        # Check for permission questions
        if any(w in reply.lower() for w in ['do you want to proceed','requires confirmation']):
            await update.message.reply_text(reply[:4000] + '\n\nReply 1=yes 2=yes,always 3=no')
            return

        # Split into bubbles by natural paragraph breaks
        bubbles = [b.strip() for b in reply.split('\n\n') if b.strip()]
        if len(bubbles) <= 1:
            bubbles = [b.strip() for b in reply.split('\n') if b.strip()]
        bubbles = bubbles[:4]

        for i, b in enumerate(bubbles):
            if i > 0:
                delay = 0.3 + len(b) * 0.02 + (hash(b[:10]) % 8) * 0.03
                await asyncio.sleep(min(delay, 5.0))
            await update.message.reply_text(b[:4000])

    except subprocess.TimeoutExpired:
        await update.message.reply_text("took too long, try again")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:500]}")
    finally:
        lock.release()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    await update.message.reply_text("ARIA ready. Flash persistent via --continue. /status")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    gpu = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used --format=csv,noheader", shell=True, capture_output=True, text=True).stdout.strip()
    await update.message.reply_text(f"GPU: {gpu}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ARIA: --continue mode (no tmux)")
    app.run_polling()

if __name__ == "__main__":
    main()
