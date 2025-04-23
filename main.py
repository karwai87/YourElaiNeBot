import os
import sys
import time
import logging
import requests
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.error import Conflict, TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import openai
import asyncio

# ─── 日志配置 ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("YourElaiNeBot")

# ─── 环境变量 ────────────────────────────────────────
load_dotenv()
BOT_TOKEN      = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USER_IDS       = {5366904723, 6069844012}

if not BOT_TOKEN or not OPENAI_API_KEY:
    logger.critical("缺少 BOT_TOKEN 或 OPENAI_API_KEY，程序终止！")
    sys.exit(1)

openai.api_key = OPENAI_API_KEY
bot            = Bot(BOT_TOKEN)
scheduler      = AsyncIOScheduler()

# ─── 节流：10秒内不重复响应 ───────────────────────────
_last: dict[int, dict[str, datetime]] = {}
def is_fast_repeat(uid: int, cmd: str) -> bool:
    now = datetime.now()
    d   = _last.setdefault(uid, {})
    prev = d.get(cmd)
    if prev and now - prev < timedelta(seconds=10):
        return True
    d[cmd] = now
    return False

# ─── Prompt 轮播 ─────────────────────────────────────
PROMPTS = [
    "a soft portrait of a slender East Asian girl in a silver qipao sitting on a sofa, natural light, soft focus",
    "an elegant East Asian girl by a window with warm sunlight, portrait style",
    "a girl in yoga pants from the back, cozy and intimate vibe",
    "a girl in an off-shoulder top reading in bed, morning light, relaxed",
    "an elegant woman with a serene smile, side profile, silk dress",
]
_idx = 0

# ─── 同步生成 & 下载图片 ──────────────────────────────
def _sync_generate(prompt: str) -> str | None:
    logger.info(f"开始生成图片：{prompt}")
    try:
        # OpenAI Python 0.27.x: 同步接口
        resp = openai.Image.create(prompt=prompt, n=1, size="600x800")
        url  = resp["data"][0]["url"]
        logger.info(f"生成成功，URL={url}")
    except Exception:
        logger.exception("调用 openai.Image.create 失败")
        return None

    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        fname = f"feifei_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        with open(fname, "wb") as f:
            f.write(r.content)
        logger.info(f"下载成功，保存到 {fname}")
        return fname
    except Exception:
        logger.exception("下载图片失败")
        return None

async def generate_image(prompt: str) -> str | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_generate, prompt)

# ─── /start ───────────────────────────────────────────
async def start_cmd(update, context):
    logger.info(f"/start 来自 {update.effective_user.id}")
    await update.message.reply_text("YourElaiNe 启动成功，欢迎回来 💡")

# ─── 发送妃妃图 ─────────────────────────────────────
async def send_feifei(update, context):
    uid = update.effective_user.id
    logger.info(f"请求妃妃图，用户={uid}")
    if uid not in USER_IDS:
        return
    if is_fast_repeat(uid, "feifei"):
        return await update.message.reply_text("稍等一下再点哦～")

    global _idx
    prompt = PROMPTS[_idx]
    _idx = (_idx + 1) % len(PROMPTS)

    try:
        fn = await generate_image(prompt)
        if not fn:
            raise RuntimeError("生成函数返回 None")
        with open(fn, "rb") as ph:
            await bot.send_photo(uid, ph, caption="晚安，这是妃妃今天的模样")
        logger.info("发送成功")
    except Exception as e:
        logger.exception("发送妃妃图时异常")
        await update.message.reply_text(f"生成失败，原因：{e}")

# ─── 定时任务 23:00 自动发 ───────────────────────────
async def scheduled_task():
    logger.info("定时任务触发")
    global _idx
    prompt = PROMPTS[_idx]
    _idx = (_idx + 1) % len(PROMPTS)

    try:
        fn = await generate_image(prompt)
        if not fn:
            raise RuntimeError("生成函数返回 None")
        for uid in USER_IDS:
            with open(fn, "rb") as ph:
                await bot.send_photo(uid, ph, caption="晚安，这是妃妃今天的模样")
        logger.info("定时发送完成")
    except Exception:
        logger.exception("定时发送失败")

# ─── 中文关键字触发 ─────────────────────────────────
async def text_filter(update, context):
    if update.effective_user.id in USER_IDS and update.message.text.strip() in {"妃妃图", "图片"}:
        await send_feifei(update, context)

# ─── 主入口 ─────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler(["feifei","pic"], send_feifei))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_filter))

    # 启动调度
    async def on_start(_):
        scheduler.add_job(scheduled_task, "cron", hour=23, minute=0)
        scheduler.start()
        logger.info("✅ Scheduler 已启动，每晚23:00自动发送")
    app.post_init = on_start

    # 保证只要抛错就重启轮询
    while True:
        try:
            logger.info("Bot 启动 run_polling() …")
            app.run_polling()
        except Conflict:
            logger.warning("Conflict，2s后重试")
            time.sleep(2)
        except TelegramError as te:
            logger.error(f"TelegramError {te}，3s后重连")
            time.sleep(3)
        except Exception:
            logger.critical("未知异常，5s后重启", exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
