# bot.py

import os
import logging
import random
import asyncio

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import openai

# —— 日志 —— #
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# —— 环境变量 —— #
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not BOT_TOKEN or not OPENAI_API_KEY:
    logger.error("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY.")
    exit(1)

# DALL·E 3 需要在你的账号里有权限
openai.api_key = OPENAI_API_KEY

# 多人白名单（逗号分隔 Chat ID），不设则不验证
_allowed = os.getenv("ALLOWED_USER_IDS")
if _allowed:
    ALLOWED_USER_IDS = set(int(x) for x in _allowed.split(",") if x.strip().isdigit())
else:
    ALLOWED_USER_IDS = None  # None 表示开放给所有人

# 预设的随机 Prompt 列表
DEFAULT_PROMPTS = [
    "妃妃身穿华丽旗袍，优雅地坐在镜头前微笑",
    "妃妃穿着汉服，在竹林中浅笑，神情温婉",
    "妃妃身着晚礼服，坐在窗前，透过窗纱的柔光微笑",
    "可爱妃妃穿着洛丽塔连衣裙，在花园里漫步微笑",
    "妃妃坐在古风庭院，身穿素雅轻纱，温柔含笑"
]

# —— /start 处理 —— #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "你好，我是 AI 妃妃机器人 🤖\n"
        "发送 /feifei <描述> 来生成妃妃的照片；\n"
        "不带描述则随机生成一张。"
    )

# —— /feifei 处理 —— #
async def feifei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # 如果设了白名单，且不在名单里，则拒绝
    if ALLOWED_USER_IDS is not None and user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("🚫 抱歉，你没有权限使用此命令。")
        return

    # 拼 Prompt
    prompt = " ".join(context.args).strip() or random.choice(DEFAULT_PROMPTS)
    await update.message.reply_text("🎨 正在根据描述生成妃妃照片，请稍候…")

    # 调用 OpenAI Image API（新版 SDK v1.x 接口）
    image_url = None
    try:
        resp = await openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            n=1
        )
        image_url = resp.data[0].url
        logger.info(f"生成成功，Prompt={prompt}，URL={image_url}")
    except Exception as e:
        logger.error(f"图像生成失败: {e}", exc_info=True)

    # 发送结果
    if image_url:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url)
    else:
        await update.message.reply_text("❌ 抱歉，生成失败，请稍后重试。")

# —— 主函数 —— #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("feifei", feifei))

    logger.info("AI 妃妃 Bot 启动……")
    app.run_polling()

if __name__ == "__main__":
    main()
