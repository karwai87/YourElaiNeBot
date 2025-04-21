import os
import asyncio
import requests
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import openai

# ─── 基础配置 ─────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("请在环境变量中设置 OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# 允许的用户列表
ALLOWED_USER_IDS = {5366904723, 6069844012}

bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

# ─── 节流控制 ─────────────────────────────────────
last_command_time: dict[int, dict[str, datetime]] = {}

def is_fast_repeat(user_id: int, cmd: str) -> bool:
    now = datetime.now()
    user_times = last_command_time.setdefault(user_id, {})
    last = user_times.get(cmd)
    if last and now - last < timedelta(seconds=10):
        return True
    user_times[cmd] = now
    return False

# ─── Prompt 轮播 ────────────────────────────────────
PROMPT_LIST = [
    "a soft portrait of a slender East Asian girl in a silver qipao sitting on a sofa, natural light, soft focus, pure girlfriend style",
    "a girl with long hair wearing a white dress sitting under window light, soft background, romantic tone",
    "a yoga pants outfit on a girl with long black hair, viewed from the back, warm tone, pure and intimate vibe",
    "a girl in an off-shoulder top reading in bed, cozy morning feeling",
    "an elegant young woman with a serene smile, side pose, wearing a satin dress, soft shadows"
]
prompt_index = 0

# ─── AI 生成函数 ────────────────────────────────────
def generate_image_sync(prompt: str) -> str | None:
    """
    同步调用 OpenAI Image API 生成一张图，并下载到本地
    返回保存的文件名，失败返回 None
    """
    try:
        resp = openai.Image.create(
            prompt=prompt,
            n=1,
            size="600x800"
        )
        img_url = resp["data"][0]["url"]
        r = requests.get(img_url, timeout=30)
        if r.status_code == 200:
            fname = f"fei_fei_{datetime.now():%Y%m%d_%H%M%S}.png"
            with open(fname, "wb") as f:
                f.write(r.content)
            return fname
    except Exception as e:
        print("生成图像出错：", e)
    return None

async def generate_image(prompt: str) -> str | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, generate_image_sync, prompt)

# ─── 发送逻辑 ──────────────────────────────────────
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

    filename = await generate_image(prompt)
    if filename:
        with open(filename, "rb") as photo:
            await bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption="晚安，这是妃妃今天的模样"
            )
    else:
        await update.message.reply_text("生成失败了，明天我补上💔")

async def scheduled_feifei():
    global prompt_index
    prompt = PROMPT_LIST[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPT_LIST)

    filename = await generate_image(prompt)
    if filename:
        with open(filename, "rb") as photo:
            for uid in ALLOWED_USER_IDS:
                await bot.send_photo(
                    chat_id=uid,
                    photo=photo,
                    caption="晚安，这是妃妃今天的模样"
                )
    else:
        print("定时生成失败，已跳过")

# 中文关键词触发
async def check_text(update, context):
    txt = update.message.text.strip()
    if update.effective_user.id in ALLOWED_USER_IDS and txt in {"妃妃图", "图片"}:
        await send_feifei(update, context)

# ─── 主入口 ───────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 支持英文指令 /feifei /pic
    app.add_handler(CommandHandler(["feifei", "pic"], send_feifei))
    # 支持中文关键词
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_text))

    # 关键：在 post_init 中注册并启动调度器
    async def start_scheduler(_):
        scheduler.add_job(scheduled_feifei, 'cron', hour=23, minute=0)
        scheduler.start()
        print("✅ Scheduler 已启动，每晚23:00自动生成并发送妃妃图")

    app.post_init = start_scheduler

    print("🤖 AI妃妃图系统启动中…")
    app.run_polling()

if __name__ == "__main__":
    main()
