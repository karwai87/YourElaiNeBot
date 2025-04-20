import os
import aiohttp
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_IDS = {5366904723}  # 你的 Telegram ID

# 初始化 Bot 和 Scheduler
bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

# 防重复节流（10 秒内不重复响应）
last_command_time = {}
def is_fast_repeat(user_id, cmd):
    now = datetime.now()
    user_times = last_command_time.setdefault(user_id, {})
    last = user_times.get(cmd)
    if last and now - last < timedelta(seconds=10):
        return True
    user_times[cmd] = now
    return False

# 轮播 Prompt 列表
PROMPT_LIST = [
    "a soft portrait of a slender East Asian girl in a silver qipao sitting on a sofa, natural light, soft focus, pure girlfriend style",
    "a girl with long hair wearing a white dress sitting under window light, soft background, romantic tone",
    "a yoga pants outfit on a girl with long black hair, viewed from the back, warm tone, pure and intimate vibe",
    "a girl in an off-shoulder top reading in bed, cozy morning feeling",
    "an elegant young woman with a serene smile, side pose, wearing a satin dress, soft shadows"
]
prompt_index = 0

# 图像生成示例（占位实现，可接 Mage/OpenAI）
async def generate_image(_prompt):
    url = "https://picsum.photos/600/800"
    filename = f"妃妃_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                with open(filename, "wb") as f:
                    f.write(data)
                return filename
    return None

# 核心发送函数
async def send_feifei(update, context):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return
    if is_fast_repeat(uid, "feifei"):
        await update.message.reply_text("稍等一下再点哦～")
        return

    global prompt_index
    prompt = PROMPT_LIST[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPT_LIST)

    file = await generate_image(prompt)
    if file:
        with open(file, "rb") as photo:
            await bot.send_photo(chat_id=update.effective_chat.id, photo=photo,
                                 caption="晚安，这是妃妃今天的模样")
    else:
        await update.message.reply_text("生成失败了，明天我补上💔")

# 定时发送任务（23:00）
async def scheduled_feifei():
    global prompt_index
    prompt = PROMPT_LIST[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPT_LIST)
    file = await generate_image(prompt)
    if file:
        with open(file, "rb") as photo:
            for uid in ALLOWED_USER_IDS:
                await bot.send_photo(chat_id=uid, photo=photo,
                                     caption="晚安，这是妃妃今天的模样")
    else:
        print("定时生成失败")

# 中文触发
async def check_text(update, context):
    txt = update.message.text.strip()
    if update.effective_user.id in ALLOWED_USER_IDS and txt in {"妃妃图", "图片"}:
        await send_feifei(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 英文命令支持
    app.add_handler(CommandHandler(["feifei", "pic"], send_feifei))
    # 中文关键词支持
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_text))

    # ▶️ 关键：在 post_init 中启动 scheduler，绝不在这里直接调用 scheduler.start()
    async def start_scheduler(_):
        scheduler.add_job(scheduled_feifei, 'cron', hour=23, minute=0)
        scheduler.start()
        print("✅ Scheduler 已启动，每晚23:00自动发妃妃图")

    app.post_init = start_scheduler

    print("🤖 AI妃妃图系统启动中…")
    app.run_polling()

if __name__ == "__main__":
    main()
