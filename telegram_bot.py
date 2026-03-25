#!/usr/bin/env python3
"""
HNLAT 自动文献下载器 - Telegram Bot

通过 Telegram 机器人远程控制文献下载

使用方法:
1. 通过 @BotFather 创建机器人，获取 token
2. 设置环境变量: export TELEGRAM_BOT_TOKEN="your_token"
3. 运行: python telegram_bot.py

支持的命令:
/doi <DOI> - 提交DOI下载
/title <标题> - 按标题下载
/parse <公众号URL> - 解析公众号文章
/status - 查看状态
/help - 帮助信息
"""

import os
import sys
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# 导入核心功能
from hnlat_auto import HNLATBot, load_config
from wechat_parser import parse_wechat_article

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 全局配置和bot实例
config = None
bot = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    await update.message.reply_text(
        "欢迎使用 HNLAT 文献下载机器人！\n\n"
        "支持的命令:\n"
        "/doi <DOI> - 提交DOI下载\n"
        "/title <标题> - 按标题下载\n"
        "/parse <公众号URL> - 解析公众号文章\n"
        "/status - 查看状态\n"
        "/help - 帮助信息"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    await update.message.reply_text(
        "使用说明:\n\n"
        "1. 通过DOI下载:\n"
        "   /doi 10.1038/s41586-024-08329-5\n\n"
        "2. 通过标题下载:\n"
        "   /title Deep learning for image recognition\n\n"
        "3. 解析公众号文章:\n"
        "   /parse https://mp.weixin.qq.com/s/xxxxx\n\n"
        "4. 查看状态:\n"
        "   /status"
    )


async def submit_doi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """提交DOI"""
    global bot
    
    if not context.args:
        await update.message.reply_text("请提供DOI，例如: /doi 10.1038/s41586-024-08329-5")
        return
    
    doi = ' '.join(context.args)
    await update.message.reply_text(f"正在提交DOI: {doi}")
    
    try:
        if not bot.logged_in:
            await update.message.reply_text("正在登录...")
            if not bot.login():
                await update.message.reply_text("登录失败，请检查配置")
                return
        
        result = bot.submit(doi=doi)
        
        if result.get("status") == 1:
            await update.message.reply_text(f"✅ 提交成功！\nDOI: {doi}\n记录编号: #{result.get('body')}")
        elif result.get("status") in (2008, 1001206):
            await update.message.reply_text(f"⏳ 该文献已在处理队列中\nDOI: {doi}")
        else:
            await update.message.reply_text(f"❌ 提交失败: {result.get('message')}")
    
    except Exception as e:
        await update.message.reply_text(f"错误: {str(e)}")


async def submit_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """提交标题"""
    global bot
    
    if not context.args:
        await update.message.reply_text("请提供论文标题，例如: /title Deep learning for image recognition")
        return
    
    title = ' '.join(context.args)
    await update.message.reply_text(f"正在提交标题: {title}")
    
    try:
        if not bot.logged_in:
            await update.message.reply_text("正在登录...")
            if not bot.login():
                await update.message.reply_text("登录失败，请检查配置")
                return
        
        result = bot.submit(title=title)
        
        if result.get("status") == 1:
            await update.message.reply_text(f"✅ 提交成功！\n标题: {title}\n记录编号: #{result.get('body')}")
        elif result.get("status") in (2008, 1001206):
            await update.message.reply_text(f"⏳ 该文献已在处理队列中\n标题: {title}")
        else:
            await update.message.reply_text(f"❌ 提交失败: {result.get('message')}")
    
    except Exception as e:
        await update.message.reply_text(f"错误: {str(e)}")


async def parse_wechat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """解析公众号文章"""
    global bot
    
    if not context.args:
        await update.message.reply_text("请提供公众号文章URL，例如: /parse https://mp.weixin.qq.com/s/xxxxx")
        return
    
    url = context.args[0]
    await update.message.reply_text(f"正在解析文章...")
    
    try:
        result = parse_wechat_article(url)
        
        if not result:
            await update.message.reply_text("❌ 解析失败，无法获取文章内容")
            return
        
        # 构建回复消息
        message = "📄 解析结果:\n\n"
        
        if result['dois']:
            message += f"找到 {len(result['dois'])} 个DOI:\n"
            for i, doi in enumerate(result['dois'], 1):
                message += f"{i}. {doi}\n"
            message += "\n"
        
        if result['titles']:
            message += f"找到 {len(result['titles'])} 个可能的标题:\n"
            for i, title in enumerate(result['titles'], 1):
                message += f"{i}. {title}\n"
            message += "\n"
        
        # 自动提交第一个可用的标识符
        if result['dois']:
            await update.message.reply_text(message + "正在自动提交第一个DOI...")
            
            if not bot.logged_in:
                bot.login()
            
            doi = result['dois'][0]
            sub_result = bot.submit(doi=doi)
            
            if sub_result.get("status") == 1:
                await update.message.reply_text(f"✅ 提交成功！\nDOI: {doi}")
            else:
                await update.message.reply_text(f"⚠️ 提交结果: {sub_result.get('message')}")
        
        elif result['titles']:
            await update.message.reply_text(message + "\n未找到DOI，请使用 /title 命令手动提交标题")
        else:
            await update.message.reply_text(message + "\n❌ 未能提取到DOI或标题")
    
    except Exception as e:
        await update.message.reply_text(f"错误: {str(e)}")


async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看状态"""
    global bot
    
    try:
        status_msg = "📊 当前状态:\n\n"
        status_msg += f"登录状态: {'✅ 已登录' if bot.logged_in else '❌ 未登录'}\n"
        status_msg += f"下载目录: {bot.download_dir}\n"
        
        # 检查邮箱
        await update.message.reply_text("正在检查邮箱...")
        emails = bot.check_mail()
        pdf_count = sum(1 for e in emails if e['has_pdf'])
        
        status_msg += f"\n📧 邮箱状态:\n"
        status_msg += f"最近邮件: {len(emails)} 封\n"
        status_msg += f"含PDF: {pdf_count} 封\n"
        
        await update.message.reply_text(status_msg)
        
        # 下载PDF
        if pdf_count > 0:
            await update.message.reply_text("正在下载PDF...")
            downloaded = bot.download_pdfs()
            if downloaded:
                await update.message.reply_text(f"✅ 已下载 {len(downloaded)} 个PDF文件")
    
    except Exception as e:
        await update.message.reply_text(f"错误: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理普通消息"""
    text = update.message.text
    
    # 检测是否为公众号链接
    if 'mp.weixin.qq.com' in text:
        await update.message.reply_text("检测到公众号链接，正在解析...")
        # 提取URL
        import re
        url_match = re.search(r'https?://[^\s]+', text)
        if url_match:
            url = url_match.group()
            context.args = [url]
            await parse_wechat(update, context)
    else:
        await update.message.reply_text(
            "收到消息。如需帮助请发送 /help\n"
            "如果发送公众号文章链接，我会自动解析其中的文献信息。"
        )


def main():
    global config, bot
    
    # 获取token
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print("错误: 请设置 TELEGRAM_BOT_TOKEN 环境变量")
        print("例如: export TELEGRAM_BOT_TOKEN='your_bot_token'")
        sys.exit(1)
    
    # 初始化配置
    try:
        config = load_config()
        bot = HNLATBot(config)
        print("✅ 配置加载成功")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        sys.exit(1)
    
    # 创建应用
    application = Application.builder().token(token).build()
    
    # 添加处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("doi", submit_doi))
    application.add_handler(CommandHandler("title", submit_title))
    application.add_handler(CommandHandler("parse", parse_wechat))
    application.add_handler(CommandHandler("status", check_status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 启动bot
    print("=" * 50)
    print("HNLAT Telegram Bot 已启动")
    print("=" * 50)
    print("\n按 Ctrl+C 停止\n")
    
    application.run_polling()


if __name__ == '__main__':
    main()
