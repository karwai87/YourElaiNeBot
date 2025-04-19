import os
import asyncio
import aiohttp
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
from chart_generator import generate_chart
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ✅ 读取 .env 文件中的 BOT_TOKEN
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ✅ Telegram 用户白名单（只能这两个 ID 使用此 Bot）
# 5366904723 = @kaven99987（主用户）
# 6069844012 = @V999887（允许访问者）
ALLOWED_USER_IDS = {5366904723, 6069844012}

# ✅ 初始化 Bot & 定时器
bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

# ✅ 每晚 11 点发送图表（给所有白名单用户）
async def send_local_chart():
    chart_path = generate_chart()
    with open(chart_path, 'rb') as photo:
        for user_id in ALLOWED_USER_IDS:
            await bot.send_photo(chat_id=user_id, photo=photo, caption="这是今日图表")

# ✅ 从远程地址抓图发送
async def send_remote_image():
    url = "https://picsum.photos/600/400"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                image_data = await resp.read()
                for user_id in ALLOWED_USER_IDS:
                    await bot.send_photo(chat_id=user_id, photo=image_data, caption="远程图片")

# ✅ 指令 /start
async def start_command(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("你无权使用此 bot")
        return
    await update.message.reply_text("YourElaiNe 已启动，欢迎回来💡")

# ✅ 指令 /sendpic：发送图表
async def sendpic_command(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("你无权使用此 bot")
        return
    await send_local_chart()

# ✅ 指令 /sendurl：发送远程图
async def sendurl_command(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("你无权使用此 bot")
        return
    await send_remote_image()

# ✅ 默认对话回应
async def echo_message(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("你无权使用此 bot")
        return
    await update.message.reply_text(f"你说了：{update.message.text}")

# ✅ 启动入口
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 指令处理器
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("sendpic", sendpic_command))
    app.add_handler(CommandHandler("sendurl", sendurl_command))

    # 默认消息处理器
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))

    # 定时任务：每天 11 点发图
    scheduler.add_job(send_local_chart, "cron", hour=23, minute=0)
    scheduler.start()

    print("Bot 运行中...")
    app.run_polling()

if __name__ == "__main__":
    main()
