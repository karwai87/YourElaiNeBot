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

# ─── 环境 & 配置 ───────────────────────────────────
load_dotenv()
BOT_TOKEN      = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USER_IDS       = {5366904723, 6069844012}

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("请先设置 BOT_TOKEN 和 OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
bot            = Bot(BOT_TOKEN)
scheduler      = AsyncIOScheduler()

# ─── 节流：10 秒内同一用户同一命令不重复响应 ──────────
last_time: dict[int, dict[str, datetime]] = {}
def is_fast_repeat(uid: int, cmd: str) -> bool:
    now = datetime.now()
    mp  = last_time.setdefault(uid, {})
    prev = mp.get(cmd)
    if prev and (now - prev) < timedelta(seconds=10):
        return True
    mp[cmd] = now
    return False

# ─── Prompt 轮播列表 ─────────────────────────────────
PROMPTS = [
    "a soft portrait of a slender East Asian girl in a silver qipao sitting on a sofa, natural light, soft focus",
    "an elegant East Asian girl by a window with warm sunlight, portrait style",
    "a girl in yoga pants from the back, cozy and intimate vibe",
    "a girl in an off-shoulder top reading in bed, morning light, relaxed",
    "an elegant woman with a serene smile, side profile, silk dress"
]
prompt_index = 0

# ─── 同步调用 OpenAI 生成并下载图片 ───────────────────
def _sync_generate(prompt: str) -> str | None:
    try:
        # 尝试新版接口
        try:
            resp = openai.images.generate(prompt=prompt, n=1, size="600x800")
            data = getattr(resp, "data", None) or resp.get("data")
            url  = data[0].get("url") if isinstance(data[0], dict) else data[0].url
        except Exception:
            # 回退旧版接口
            resp = openai.Image.create(prompt=prompt, n=1, size="600x800")
            url  = resp["data"][0]["url"]

        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            fname = f"feifei_{datetime.now():%Y%m%d_%H%M%S}.jpg"
            with open(fname, "wb") as f:
                f.write(r.content)
            return fname
        else:
            print(f"❌ 下载图片失败，HTTP {r.status_code}")
    except Exception as e:
        print("❌ 生成图像出错：", e)
    return None

async def generate_image(prompt: str) -> str | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_generate, prompt)

# ─── /start 命令 ─────────────────────────────────────
async def start_command(update, context):
    await update.message.reply_text("YourElaiNe 启动成功，欢迎回来 💡")

# ─── 手动触发 & 英文命令 (/feifei /pic) ─────────────
async def send_feifei(update, context):
    uid = update.effective_user.id
    if uid not in USER_IDS:
        return
    if is_fast_repeat(uid, "feifei"):
        return await update.message.reply_text("稍等一下再点哦～")

    global prompt_index
    prompt = PROMPTS[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPTS)

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

# ─── 定时任务：23:00 自动发送 ─────────────────────────
async def scheduled_feifei():
    global prompt_index
    prompt = PROMPTS[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPTS)

    filename = await generate_image(prompt)
    if filename:
        for uid in USER_IDS:
            with open(filename, "rb") as photo:
                await bot.send_photo(
                    chat_id=uid,
                    photo=photo,
                    caption="晚安，这是妃妃今天的模样"
                )
    else:
        print("⚠️ 定时生成失败，已跳过")

# ─── 中文关键词触发 ─────────────────────────────────
async def check_text(update, context):
    txt = update.message.text.strip()
    if update.effective_user.id in USER_IDS and txt in {"妃妃图", "图片"}:
        await send_feifei(update, context)

# ─── 主入口 & 冲突重试 ─────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    # handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler(["feifei","pic"], send_feifei))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_text))

    # scheduler
    async def start_sched(_):
        scheduler.add_job(scheduled_feifei, "cron", hour=23, minute=0)
        scheduler.start()
        print("✅ Scheduler 已启动，每晚23:00自动发送")
    app.post_init = start_sched

    # 重试循环，捕获 Conflict/超时 等
    while True:
        try:
            print("🤖 AI妃妃Bot 启动中…")
            app.run_polling()
        except Conflict:
            print("⚠️ 检测到冲突，2秒后重试…")
            time.sleep(2)
        except TelegramError as te:
            print("⚠️ TelegramError:", te, " 3秒后重试…")
            time.sleep(3)
        except Exception as e:
            print("🔥 未捕获异常:", e, " 5秒后重启…")
            time.sleep(5)

if __name__ == "__main__":
    main()
