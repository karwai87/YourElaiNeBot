import os
import logging
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import openai

# --- Configuration & Logging ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
                    level=logging.INFO)
logger = logging.getLogger("YourElaiNeBot")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    logger.error("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY.")
    raise RuntimeError("Please provide TELEGRAM_BOT_TOKEN and OPENAI_API_KEY environment vars.")

openai.api_key = OPENAI_API_KEY

# --- Command Handlers ---
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "你好，我是问答机器人！发送 /ask 加上你的问题，例如：\n/ask 今天天气如何？"
    )

async def ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    question = " ".join(ctx.args)
    if not question:
        return await update.message.reply_text("请在 /ask 后输入你的问题。")
    msg = await update.message.reply_text("🕐 正在思考，请稍候…")
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": question}],
            max_tokens=500,
            temperature=0.7,
        )
        answer = resp.choices[0].message.content.strip()
        await msg.edit_text(answer)
    except Exception as e:
        logger.exception("问答时发生异常")
        await msg.edit_text(f"❌ 回答失败：{e}")

# --- Fallback Echo ---
async def echo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "未识别命令，请使用 /ask 提问，或 /start 查看帮助。"
    )

# --- Main ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    logger.info("YourElaiNeBot AI问答系统启动，开始 run_polling()…")
    app.run_polling()

if __name__ == "__main__":
    main()
