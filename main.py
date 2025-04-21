import os
import asyncio
import requests
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import openai

# ─── 读取环境变量 ──────────────────────────────────
load_dotenv()
BOT_TOKEN       = os.getenv("BOT_TOKEN")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
USER_IDS        = {5366904723, 6069844012}

if not (BOT_TOKEN and OPENAI_API_KEY):
    raise RuntimeError("请检查 BOT_TOKEN 与 OPENAI_API_KEY 是否已设置")

openai.api_key = OPENAI_API_KEY
bot             = Bot(token=BOT_TOKEN)
scheduler       = AsyncIOScheduler()

# ─── 节流保护：10秒内同一指令不重复响应 ──────────────
last_time: dict[int, dict[str, datetime]] = {}
def is_fast_repeat(user_id: int, cmd: str) -> bool:
    now = datetime.now()
    user_map = last_time.setdefault(user_id, {})
    prev = user_map.get(cmd)
    if prev and (now - prev) < timedelta(seconds=10):
        return True
    user_map[cmd] = now
    return False

# ─── Prompt 轮播列表 ─────────────────────────────────
PROMPTS = [
    "a soft portrait of a slender East Asian girl in a silver qipao sitting on a sofa, natural light, soft focus, pure girlfriend style",
    "a girl with long hair wearing a white dress seated by the window, gentle sunlight, warm tone",
    "a yoga pants outfit on a girl from the back, long black hair, intimate and cozy vibe",
    "a girl in an off-shoulder top reading in bed, morning light, soft and relaxed",
    "an elegant young woman with a serene smile, side pose, silk dress, soft shadows"
]
prompt_index = 0

# ─── 同步调用 OpenAI 生成图像并下载 ─────────────────
def _sync_generate(prompt: str) -> str|None:
    try:
        res = openai.Image.create(prompt=prompt, n=1, size="600x800")
        url = res["data"][0]["url"]
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            fname = f"feifei_{datetime.now():%Y%m%d_%H%M%S}.jpg"
            with open(fname, "wb") as f:
                f.write(r.content)
            return fname
    except Exception as e:
        print("❌ 生成图像出错：", e)
    return None

async def generate_image(prompt: str) -> str|None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_generate, prompt)

# ─── 核心发送函数 ────────────────────────────────
async def send_feifei(update, context):
    uid = update.effective_user.id
    if uid not in USER_IDS:
        return
    if is_fast_repeat(uid, "feifei"):
        return await update.message.reply_text("稍等一下再点哦～")

    global prompt_index
    prompt = PROMPTS[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPTS)

    fname = await generate_image(prompt)
    if fname:
        with open(fname, "rb") as photo:
            await bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption="晚安，这是妃妃今天的模样"
            )
    else:
        await update.message.reply_text("生成失败了，明天我补上💔")

# ─── 定时任务：每晚23:00自动发 ─────────────────────
async def scheduled_feifei():
    global prompt_index
    prompt = PROMPTS[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPTS)
    fname = await generate_image(prompt)
    if fname:
        with open(fname, "rb") as photo:
            for uid in USER_IDS:
                await bot.send_photo(chat_id=uid, photo=photo,
                                     caption="晚安，这是妃妃今天的模样")
    else:
        print("⚠️ 定时生成失败，跳过")

# ─── 中文关键词触发 ─────────────────────────────────
async def check_text(update, context):
    txt = update.message.text.strip()
    if update.effective_user.id in USER_IDS and txt in {"妃妃图", "图片"}:
        await send_feifei(update, context)

# ─── 启动入口 ─────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 英文命令
    app.add_handler(CommandHandler(["feifei", "pic"], send_feifei))
    # 中文触发
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_text))

    # 关键：在 post_init 里启动 Scheduler
    async def start_sched(_):
        scheduler.add_job(scheduled_feifei, "cron", hour=23, minute=0)
        scheduler.start()
        print("✅ Scheduler 已启动，每晚23:00自动发送")
    app.post_init = start_sched

    print("🤖 AI妃妃Bot 启动中…")
    app.run_polling()

if __name__ == "__main__":
    main()
