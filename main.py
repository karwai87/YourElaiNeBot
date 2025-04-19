import os
import asyncio
import aiohttp
from telegram import Bot
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv
from chart_generator import generate_chart
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
USER_ID = int(os.getenv("USER_ID"))

bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

async def send_local_chart():
    chart_path = generate_chart()
    with open(chart_path, 'rb') as photo:
        await bot.send_photo(chat_id=USER_ID, photo=photo, caption="这是今日图表")

async def send_remote_image():
    url = "https://picsum.photos/600/400"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                image_data = await resp.read()
                await bot.send_photo(chat_id=USER_ID, photo=image_data, caption="远程图片")

async def sendpic_command(update, context):
    await send_local_chart()

async def sendurl_command(update, context):
    await send_remote_image()

async def start_command(update, context):
    await update.message.reply_text("YourElaiNe 已启动，可自动发送图片")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("sendpic", sendpic_command))
    app.add_handler(CommandHandler("sendurl", sendurl_command))
    scheduler.add_job(send_local_chart, "cron", hour=23, minute=0)
    scheduler.start()
    print("Bot 运行中...")
    app.run_polling()

if __name__ == "__main__":
    main()
