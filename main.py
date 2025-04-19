import os
import asyncio
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import aiohttp

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_IDS = {5366904723}  # 你的 Telegram ID

bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

# 节流控制（10秒）
last_command_time = {}

# Prompt 轮播
PROMPT_LIST = [
    "a soft portrait of a slender East Asian girl in a silver qipao sitting on a sofa, natural light, soft focus, pure girlfriend style",
    "a girl with long hair wearing a white dress sitting under window light, soft background, romantic tone",
    "a yoga pants outfit on a girl with long black hair, viewed from the back, warm tone, pure and intimate vibe",
    "a girl in an off-shoulder top reading in bed, cozy morning feeling",
    "an elegant young woman with a serene smile, side pose, wearing a satin dress, soft shadows"
]
prompt_index = 0

# 模拟图像生成函数
async def generate_image(prompt_text):
    url = "https://picsum.photos/600/800"
    filename = "妃妃_{}.jpg".format(datetime.now().strftime('%Y%m%d'))
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                image_data = await resp.read()
                with open(filename, 'wb') as f:
                    f.write(image_data)
                return filename
    return None

def is_fast_repeat(user_id, command_name):
    now = datetime.now()
    if user_id not in last_command_time:
        last_command_time[user_id] = {}
    last_time = last_command_time[user_id].get(command_name)
    if last_time and now - last_time < timedelta(seconds=10):
        return True
    last_command_time[user_id][command_name] = now
    return False

# 主图发送函数
async def send_feifei(update, context):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        return
    if is_fast_repeat(update.effective_user.id, '妃妃图'):
        await update.message.reply_text("慢一点啦～稍后再点 🕒")
        return

    global prompt_index
    prompt = PROMPT_LIST[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPT_LIST)
    filename = await generate_image(prompt)
    if filename:
        with open(filename, 'rb') as photo:
            await bot.send_photo(chat_id=update.effective_chat.id, photo=photo,
                                 caption="晚安，这是妃妃今天的模样")
    else:
        await update.message.reply_text("图像生成失败，明天我补上 💔")

# 定时任务发送
async def scheduled_feifei():
    global prompt_index
    prompt = PROMPT_LIST[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPT_LIST)
    filename = await generate_image(prompt)
    if filename:
        with open(filename, 'rb') as photo:
            for uid in ALLOWED_USER_IDS:
                await bot.send_photo(chat_id=uid, photo=photo, caption="晚安，这是妃妃今天的模样")
    else:
        print("定时妃妃图生成失败")

# 中文触发器
async def check_chinese_request(update, context):
    text = update.message.text.strip()
    if update.effective_user.id in ALLOWED_USER_IDS:
        if text in ["妃妃图", "图片"]:
            await send_feifei(update, context)

# 启动
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 英文命令支持
    app.add_handler(CommandHandler(["feifei", "pic"], send_feifei))

    # 中文关键词识别
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_chinese_request))

    scheduler.add_job(scheduled_feifei, 'cron', hour=23, minute=0)
    scheduler.start()

    print("AI妃启动中...")
    app.run_polling()

if __name__ == "__main__":
    main()
