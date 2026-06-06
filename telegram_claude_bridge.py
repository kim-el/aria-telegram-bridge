import os, subprocess, asyncio, threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
os.environ["ANTHROPIC_API_KEY"] = os.environ["DEEPSEEK_KEY"] = "sk-5b400a3177cb44089b29915c231edb5f"
os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
FLASH = {**os.environ, "ANTHROPIC_MODEL": "deepseek-v4-flash"}
PRO = {**os.environ, "ANTHROPIC_MODEL": "deepseek-v4-pro", "ANTHROPIC_SMALL_FAST_MODEL": "deepseek-v4-flash"}
lock = threading.Lock()

def claude_ask(prompt, env, max_turns=3, timeout=600):
    r = subprocess.run(
        ["claude", "-p", prompt, "--permission-mode", "auto",
         "--max-turns", str(max_turns), "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout,
        cwd="/root", env={**os.environ, **env, "HOME": "/root"}
    )
    return (r.stdout + r.stderr).strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.text
    if not lock.acquire(blocking=False):
        await update.message.reply_text("one sec...")
        return
    try:
        # ── Pipeline: Flash ack → Pro thinks → Flash presents ──

        # Layer 1: Flash instant ack
        ack = claude_ask(
            f"User said: '{msg}'. Reply with a short casual acknowledgment. Under 5 words. Be natural. Just the phrase, nothing else.",
            FLASH, max_turns=1, timeout=10
        )
        if ack:
            await update.message.reply_text(ack.strip()[:200])

        # Layer 2: Pro does the real work
        await update.message.chat.send_action("typing")
        pro_reply = claude_ask(
            f"You are ARIA, a helpful assistant running on a GPU server. Answer concisely. You can use bash to check things.\n\nUser: {msg}",
            PRO, max_turns=20, timeout=600
        )
        if not pro_reply:
            await update.message.reply_text("hmm, got nothing back. try again?")
            return

        # Check for permission questions
        if any(w in pro_reply.lower() for w in ['do you want to proceed','requires confirmation','auto mode classifier']):
            await update.message.reply_text(pro_reply[:4000] + '\n\nReply 1=yes 2=yes,always 3=no')
            return

        # Layer 3: Flash reformats Pro's answer into chat bubbles
        await update.message.chat.send_action("typing")
        chat = claude_ask(
            f"Rewrite this as 2-4 casual text messages. One sentence per line. No markdown, no emojis. Keep key facts. Sound like a friend texting:\n\n{pro_reply}",
            FLASH, max_turns=1, timeout=15
        )
        formatted = chat if chat else pro_reply

        # Send as bubbles
        bubbles = [b.strip() for b in formatted.split('\n') if b.strip()][:4]
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
