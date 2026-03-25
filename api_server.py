#!/usr/bin/env python3
"""
HNLAT 自动文献下载器 - Web API 服务

提供HTTP接口用于：
- 提交DOI/标题下载文献
- 解析公众号文章
- 检查邮箱状态
- 下载PDF

启动: python api_server.py
默认端口: 5000
"""

import json
import sys
from pathlib import Path
from flask import Flask, request, jsonify

# 导入核心功能
from hnlat_auto import HNLATBot, load_config
from wechat_parser import parse_wechat_article

app = Flask(__name__)

# 全局配置和bot实例
config = None
bot = None


@app.before_request
def initialize():
    """初始化配置和bot"""
    global config, bot
    if config is None:
        try:
            config = load_config()
            bot = HNLATBot(config)
        except Exception as e:
            print(f"初始化失败: {e}")
            sys.exit(1)


@app.route('/')
def index():
    """API首页"""
    return jsonify({
        "name": "HNLAT Paper Downloader API",
        "version": "1.0.0",
        "endpoints": {
            "POST /submit": "提交文献（doi或title参数）",
            "POST /parse_wechat": "解析公众号文章（url参数）",
            "GET /check_mail": "检查邮箱",
            "GET /download": "下载PDF",
            "GET /status": "获取状态"
        }
    })


@app.route('/submit', methods=['POST'])
def submit():
    """
    提交文献到HNLAT
    
    请求体:
    {
        "doi": "10.1038/xxx"  或
        "title": "paper title"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400
    
    doi = data.get('doi')
    title = data.get('title')
    
    if not doi and not title:
        return jsonify({"error": "需要提供doi或title参数"}), 400
    
    # 登录
    if not bot.logged_in:
        if not bot.login():
            return jsonify({"error": "登录失败"}), 500
    
    # 提交
    try:
        result = bot.submit(doi=doi or "", title=title or "")
        return jsonify({
            "success": result.get("status") == 1,
            "status": result.get("status"),
            "message": result.get("message"),
            "data": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/parse_wechat', methods=['POST'])
def parse_wechat():
    """
    解析公众号文章
    
    请求体:
    {
        "url": "https://mp.weixin.qq.com/s/xxxxx",
        "auto_submit": false  # 是否自动提交到HNLAT
    }
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "需要提供url参数"}), 400
    
    url = data['url']
    auto_submit = data.get('auto_submit', False)
    
    try:
        result = parse_wechat_article(url)
        if not result:
            return jsonify({"error": "解析失败"}), 500
        
        response = {
            "success": True,
            "url": url,
            "dois": result.get('dois', []),
            "titles": result.get('titles', []),
            "journals": result.get('journals', [])
        }
        
        # 自动提交
        if auto_submit:
            submissions = []
            if not bot.logged_in:
                bot.login()
            
            for doi in result.get('dois', []):
                sub_result = bot.submit(doi=doi)
                submissions.append({
                    "type": "doi",
                    "value": doi,
                    "result": sub_result
                })
            
            if not submissions and result.get('titles'):
                sub_result = bot.submit(title=result['titles'][0])
                submissions.append({
                    "type": "title",
                    "value": result['titles'][0],
                    "result": sub_result
                })
            
            response['submissions'] = submissions
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/check_mail', methods=['GET'])
def check_mail():
    """检查邮箱状态"""
    try:
        emails = bot.check_mail()
        return jsonify({
            "success": True,
            "count": len(emails),
            "emails": emails
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download', methods=['GET'])
def download():
    """下载PDF"""
    try:
        downloaded = bot.download_pdfs()
        return jsonify({
            "success": True,
            "count": len(downloaded),
            "files": downloaded
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    """获取服务状态"""
    return jsonify({
        "status": "running",
        "logged_in": bot.logged_in if bot else False,
        "download_dir": str(bot.download_dir) if bot else None
    })


if __name__ == '__main__':
    print("=" * 50)
    print("HNLAT Paper Downloader API Server")
    print("=" * 50)
    print("\n启动服务...")
    print("API地址: http://localhost:5000")
    print("\n按 Ctrl+C 停止服务\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
