# -*- coding: utf-8 -*-
# 导入所需的库
import os
import logging
import asyncio
import traceback

import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# 配置基本日志格式和级别（信息级别以上的日志都会输出）
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 从环境变量获取 Telegram Bot Token 和 OpenAI API 密钥
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not TOKEN or not OPENAI_API_KEY:
    logger.error("未提供 TELEGRAM_BOT_TOKEN 或 OPENAI_API_KEY 环境变量")
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY.")

# 设置 OpenAI API 密钥
openai.api_key = OPENAI_API_KEY

# 可选：开发者（管理员）Chat ID，用于接收错误通知（从环境变量读取，如未设置则为 None）
DEVELOPER_CHAT_ID = os.getenv("DEVELOPER_CHAT_ID")
if DEVELOPER_CHAT_ID:
    try:
        DEVELOPER_CHAT_ID = int(DEVELOPER_CHAT_ID)
    except ValueError:
        logger.error("DEVELOPER_CHAT_ID 环境变量不是有效的整数，已忽略。")
        DEVELOPER_CHAT_ID = None

# 异步函数：使用 OpenAI 图像生成 API 获取图像 URL
async def generate_image(prompt: str) -> str:
    """
    调用 OpenAI 的图像生成接口，根据提示词生成一张图片，返回图片的 URL。
    如果调用失败，将记录错误并抛出异常。
    """
    try:
        # OpenAI Image.create 为阻塞调用，这里在线程池中执行以避免阻塞事件循环&#8203;:contentReference[oaicite:6]{index=6}
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: openai.Image.create(prompt=prompt, n=1, size="512x512")
        )
        # 从响应中提取生成的图片 URL（假设只生成 1 张图片）
        image_url = response["data"][0]["url"]
        return image_url  # 确保返回 URL，而非 None
    except Exception as e:
        # 记录错误日志，包含堆栈信息&#8203;:contentReference[oaicite:7]{index=7}
        logger.error(f"调用 OpenAI 接口生成图像失败: {e}", exc_info=True)
        # （可选）在此直接通知开发者发生错误
        # if DEVELOPER_CHAT_ID:
        #     await context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=f"Image gen error:\n{traceback.format_exc()}")
        # 将异常继续抛出，以便上层处理
        raise

# /start 命令处理器
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /start 命令，发送欢迎信息。
    """
    user = update.effective_user
    welcome_text = (
        f"你好，{user.first_name}！\n"
        "我是一个OpenAI图像生成机器人，你可以通过发送 /feifei 命令来生成图片。"
    )
    await update.message.reply_text(welcome_text)
    # （可选）告诉开发者他们的 chat_id 以便调试或接收错误通知
    # await update.message.reply_text(f"你的聊天 ID 是：{update.effective_chat.id}")

# /feifei 命令处理器
async def feifei(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /feifei 命令。根据用户提供的描述文本生成图像，并将图像发送给用户。
    """
    # 获取命令参数作为图像生成的提示(prompt)
    prompt = " ".join(context.args) if context.args else ""
    if not prompt:
        # 如果用户未提供描述，提示用法
        await update.message.reply_text("请在命令后提供图片描述，例如：/feifei 可爱的机器人。")
        return

    # 通知用户我们开始生成图片（因为可能需要几秒钟）
    await update.message.reply_text("🎨 正在根据描述生成图片，请稍候...")

    try:
        # 调用异步的图像生成函数获取图片 URL
        image_url = await generate_image(prompt)
        # 通过 Telegram API 发送照片给用户（直接使用 URL，Telegram 会自行下载并发送图片）
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url)
        logger.info(f"已为用户 {update.effective_chat.id} 生成图片: {prompt}")
    except Exception as e:
        # 捕获生成过程中的异常，反馈给用户并通知开发者
        error_text = "抱歉，生成图像时出现错误，请稍后重试。"
        await update.message.reply_text(error_text)
        # 如果设置了开发者 Chat ID，则发送错误详情
        if DEVELOPER_CHAT_ID:
            err_info = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            await context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=f"错误通知:\n{err_info}")
        # 日志中已经记录详细错误，无需再次抛出异常

# 全局错误处理器：捕获任何未捕获的异常&#8203;:contentReference[oaicite:8]{index=8}&#8203;:contentReference[oaicite:9]{index=9}
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    全局错误处理函数。当更新处理过程中发生未捕获异常时调用。
    记录错误日志，并通过 Telegram 将异常通知给开发者（如果已配置）。
    """
    # 日志记录错误详情
    logger.error("处理更新时发生异常", exc_info=context.error)
    # 将异常发送给开发者
    if DEVELOPER_CHAT_ID:
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_text = "".join(tb_list)
        await context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=f"机器人发生异常:\n<pre>{tb_text}</pre>", parse_mode="HTML")

def main() -> None:
    """主函数：初始化并启动 Telegram Bot。"""
    # 创建 Application 实例并添加命令处理器
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("feifei", feifei))
    application.add_error_handler(error_handler)  # 注册全局错误处理

    # 启动轮询服务，开始接收消息
    logger.info("🤖 机器人正在启动，开始轮询消息...")
    application.run_polling()
    # 注意：请勿重复调用 run_polling()，也不要在多个进程中并发运行此脚本&#8203;:contentReference[oaicite:10]{index=10}

if __name__ == "__main__":
    main()
