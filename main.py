import os
import time
import asyncio
import requests
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.error import Conflict, TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import openai

# ─── 环境变量 ───────────────────────────────────
load_dotenv()
BOT_TOKEN      = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USER_IDS       = {5366904723, 6069844012}

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("请设置 BOT_TOKEN 和 OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
bot            = Bot(BOT_TOKEN)
scheduler      = AsyncIOScheduler()

# ─── 节流保护：10 秒内同指令不重复 ───────────────
_last_times: dict[int, dict[str, datetime]] = {}
def is_fast_repeat(uid: int, cmd: str) -> bool:
    now = datetime.now()
    user_map = _last_times.setdefault(uid, {})
    prev = user_map.get(cmd)
    if prev and (now - prev) < timedelta(seconds=10):
        return True
    user_map[cmd] = now
    return False

# ─── Prompt 轮播列表 ───────────────────────────────
PROMPTS = [
    "a soft portrait of a slender East Asian girl in a silver qipao sitting on a sofa, natural light, soft focus",
    "a girl in a white dress by a window with warm sunlight, gentle atmosphere",
    "a yoga pants outfit on a girl from the back, intimate cozy vibe",
    "a girl in an off-shoulder top reading in bed, morning light, relaxed mood",
    "an elegant young woman with serene smile, side pose, silk dress, soft shadows"
]
_prompt_index = 0

# ─── 同步调用 OpenAI Images API 并下载 ───────────────
def _sync_generate(prompt: str) -> str | None:
    try:
        resp = openai.images.generate(prompt=prompt, n=1, size="600x800")
        url  = resp.data[0].url
        r    = requests.get(url, timeout=30)
        if r.status_code == 200:
            fname = f"feifei_{datetime.now():%Y%m%d_%H%M%S}.jpg"
            with open(fname, "wb") as f:
                f.write(r.content)
            return fname
    except Exception as e:
        print("❌ 生成图像出错：", e)
    return None

async def generate_image(prompt: str) -> str | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_generate, prompt)

# ─── /start 指令 ─────────────────────────────────
async def start_command(update, context):
    await update.message.reply_text("YourElaiNe 启动成功，欢迎回来 💡")

# ─── 发送妃妃图核心函数 ────────────────────────────
async def send_feifei(update, context):
    uid = update.effective_user.id
    if uid not in USER_IDS:
        return
    if is_fast_repeat(uid, "feifei"):
        return await update.message.reply_text("稍等一下再点哦～")

    global _prompt_index
    prompt = PROMPTS[_prompt_index]
    _prompt_index = (_prompt_index + 1) % len(PROMPTS)

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

# ─── 每晚23:00定时发送 ────────────────────────────
async def scheduled_feifei():
    global _prompt_index
    prompt = PROMPTS[_prompt_index]
    _prompt_index = (_prompt_index + 1) % len(PROMPTS)
    fname = await generate_image(prompt)
    if fname:
        for uid in USER_IDS:
            with open(fname, "rb") as photo:
                await bot.send_photo(uid, photo, caption="晚安，这是妃妃今天的模样")
    else:
        print("⚠️ 定时生成失败，已跳过")

# ─── 中文关键词触发 ─────────────────────────────────
async def check_text(update, context):
    txt = update.message.text.strip()
    if update.effective_user.id in USER_IDS and txt in {"妃妃图", "图片"}:
        await send_feifei(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 注册 handler
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler(["feifei", "pic"], send_feifei))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_text))

    # 定时任务在事件循环就绪后启动
    async def start_scheduler(_):
        scheduler.add_job(scheduled_feifei, "cron", hour=23, minute=0)
        scheduler.start()
        print("✅ Scheduler 已启动，每晚23:00自动发送")
    app.post_init = start_scheduler

    # ✨ 重试机制：捕获 Conflict 和其他异常，自动重启轮询
    while True:
        try:
            print("🤖 AI妃妃 Bot 进入轮询…")
            app.run_polling()
        except Conflict:
            print("⚠️ 检测到冲突，2秒后重试…")
            time.sleep(2)
        except TelegramError as e:
            print(f"🔥 TelegramError，3秒后重试：{e}")
            time.sleep(3)
        except Exception as e:
            print(f"🔥 未知异常，3秒后重试：{e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
