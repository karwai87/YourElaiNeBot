import os
import sys
import time
import io
import asyncio
import requests
import logging
from datetime import datetime, timedelta
from telegram import Bot, InputFile
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

# ─── 日志配置 ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("YourElaiNeBot")

# ─── 加载环境变量 ────────────────────────────────────
load_dotenv()
BOT_TOKEN      = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USER_IDS       = {5366904723, 6069844012}

if not BOT_TOKEN or not OPENAI_API_KEY:
    logger.critical("缺少 BOT_TOKEN 或 OPENAI_API_KEY，程序终止！")
    sys.exit(1)

openai.api_key = OPENAI_API_KEY

bot       = Bot(BOT_TOKEN)
scheduler = AsyncIOScheduler()

# ─── 节流：10秒内同一用户同一命令不重复响应 ─────────────
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
    "an elegant woman with a serene smile, side profile, silk dress",
]
prompt_index = 0

# ─── 同步生成并下载图片 ─────────────────────────────────
def _sync_generate(prompt: str) -> str | None:
    logger.info(f"开始生成图片，prompt：{prompt}")
    try:
        # 新版接口
        resp = openai.images.generate(prompt=prompt, n=1, size="600x800")
        data = getattr(resp, "data", None) or resp.get("data")
        url  = data[0].url if hasattr(data[0], "url") else data[0]["url"]
    except Exception as e1:
        logger.warning("openai.images.generate 调用失败，尝试回退旧版接口", exc_info=e1)
        try:
            resp = openai.Image.create(prompt=prompt, n=1, size="600x800")
            url  = resp["data"][0]["url"]
        except Exception as e2:
            logger.exception("openai.Image.create 也调用失败，无法生成图片")
            return None

    logger.info(f"下载图片 URL：{url}")
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        fname = f"feifei_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        with open(fname, "wb") as f:
            f.write(r.content)
        logger.info(f"图片已下载到本地：{fname}")
        return fname
    except Exception:
        logger.exception("下载图片失败")
        return None

async def generate_image(prompt: str) -> str | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_generate, prompt)

# ─── /start 命令 ─────────────────────────────────────
async def start_command(update, context):
    user = update.effective_user
    logger.info(f"/start 来自 @{user.username} ({user.id})")
    await update.message.reply_text("YourElaiNe 启动成功，欢迎回来 💡")

# ─── 发送妃妃图 ─────────────────────────────────────
async def send_feifei(update, context):
    user = update.effective_user
    logger.info(f"发送妃妃图请求，来自 @{user.username} ({user.id})")
    if user.id not in USER_IDS:
        logger.warning(f"未授权用户 {user.id} 试图调用 send_feifei")
        return

    if is_fast_repeat(user.id, "feifei"):
        logger.info("节流：10秒内重复调用，已忽略")
        return await update.message.reply_text("稍等一下再点哦～")

    global prompt_index
    prompt = PROMPTS[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPTS)

    try:
        filename = await generate_image(prompt)
        if not filename:
            raise RuntimeError("生成函数返回 None")
        with open(filename, "rb") as photo:
            await bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption="晚安，这是妃妃今天的模样"
            )
        logger.info(f"妃妃图已发送给 {user.id}")
    except Exception as e:
        logger.exception("发送妃妃图时发生异常")
        await update.message.reply_text(f"生成失败，原因：{e}")

# ─── 定时任务：23:00 自动发图 ─────────────────────────
async def scheduled_feifei():
    logger.info("定时任务触发：scheduled_feifei()")
    global prompt_index
    prompt = PROMPTS[prompt_index]
    prompt_index = (prompt_index + 1) % len(PROMPTS)

    try:
        filename = await generate_image(prompt)
        if not filename:
            raise RuntimeError("生成函数返回 None")
        for uid in USER_IDS:
            with open(filename, "rb") as photo:
                await bot.send_photo(uid, photo, caption="晚安，这是妃妃今天的模样")
        logger.info("定时妃妃图发送完成")
    except Exception:
        logger.exception("定时发送妃妃图失败")

# ─── 中文关键词触发 ─────────────────────────────────
async def check_text(update, context):
    txt = update.message.text.strip()
    user = update.effective_user
    if user.id in USER_IDS and txt in {"妃妃图", "图片"}:
        await send_feifei(update, context)

# ─── 主入口 & 冲突重试 ─────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 注册 Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler(["feifei","pic"], send_feifei))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_text))

    # 启动调度器
    async def start_sched(_):
        scheduler.add_job(scheduled_feifei, "cron", hour=23, minute=0)
        scheduler.start()
        logger.info("✅ Scheduler 已启动，每晚23:00自动发送")
    app.post_init = start_sched

    # 循环重试，防冲突/超时导致退出
    while True:
        try:
            logger.info("🤖 AI妃妃Bot 启动中，开始 run_polling() …")
            app.run_polling()
        except Conflict:
            logger.warning("Conflict: 其他轮询占用，2秒后重试…")
            time.sleep(2)
        except TelegramError as te:
            logger.error(f"TelegramError: {te} 3秒后重试…")
            time.sleep(3)
        except Exception as e:
            logger.critical(f"未捕获异常: {e}，5秒后重启…", exc_info=e)
            time.sleep(5)

if __name__ == "__main__":
    main()
