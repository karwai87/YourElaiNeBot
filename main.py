import os
import asyncio
import aiohttp
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
from chart_generator import generate_chart
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 加载 .env 环境变量
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Telegram 白名单
# 5366904723 = @kaven99987
# 6069844012 = @V999887
ALLOWED_USER_IDS = {5366904723, 6069844012}

# 初始化
bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

# 每晚定时任务
async def send_local_chart():
    chart_path = generate_chart()
    with open(chart_path, 'rb') as photo:
        for user_id in ALLOWED_USER_IDS:
            await bot.send_photo(chat_id=user_id, photo=photo, caption="这是今日图表")

# 远程图片
async def send_remote_image():
    url = "https://picsum.photos/600/400"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                image_data = await resp.read()
                for user_id in ALLOWED_USER_IDS:
                    await bot.send_photo(chat_id=user_id, photo=image_data, caption="远程图片")

# Bot 指令
async def start_command(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("你无权使用此 bot")
        return
    await update.message.reply_text("YourElaiNe 启动成功，欢迎回来 💡")

async def sendpic_command(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("你无权使用此 bot")
        return
    await send_local_chart()

async def sendurl_command(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("你无权使用此 bot")
        return
    await send_remote_image()

async def echo_message(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("你无权使用此 bot")
        return
    await update.message.reply_text(f"你说了：{update.message.text}")

# 🛠️ Scheduler 启动逻辑（避免 crash）
async def start_scheduler(app):
    scheduler.add_job(send_local_chart, "cron", hour=23, minute=0)
    scheduler.start()
    print("Scheduler 已启动...")

# 主函数
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("sendpic", sendpic_command))
    app.add_handler(CommandHandler("sendurl", sendurl_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))

    app.post_init = start_scheduler  # 确保 scheduler 在 asyncio loop 内启动
    print("Bot 运行中...")
    app.run_polling()

if __name__ == "__main__":
    main()
