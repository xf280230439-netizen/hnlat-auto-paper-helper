#!/usr/bin/env python3
"""
微信公众号文章科研文献自动解析工具

功能：
1. 解析公众号文章链接，提取其中提到的科研文献信息（DOI或标题）
2. 支持从文章正文图片（如标题截图）中 OCR 识别文字
3. 自动调用 hnlat_auto.py 提交并下载文献

使用方法：
python wechat_parser.py <公众号文章URL>
python wechat_parser.py <URL> --ocr          # 启用图片OCR（默认启用）
python wechat_parser.py <URL> --no-ocr       # 禁用图片OCR
python wechat_parser.py <URL> --submit       # 解析并自动提交
"""

import argparse
import re
import json
import requests
import sys
import io
import os
import tempfile
from urllib.parse import urlparse, urljoin
from html import unescape
from pathlib import Path


# ─────────────────────────── OCR 引擎加载 ───────────────────────────

def _try_load_paddleocr():
    """尝试加载 PaddleOCR（精度最高，支持中英文）"""
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        return ('paddleocr', ocr)
    except Exception:
        return None


def _try_load_easyocr():
    """尝试加载 EasyOCR（精度好，中英文均支持）"""
    try:
        import easyocr
        reader = easyocr.Reader(['en', 'ch_sim'], verbose=False)
        return ('easyocr', reader)
    except Exception:
        return None


def _try_load_pytesseract():
    """尝试加载 pytesseract（Tesseract，需本地安装）"""
    try:
        import pytesseract
        from PIL import Image
        # 简单测试
        pytesseract.get_tesseract_version()
        return ('tesseract', pytesseract)
    except Exception:
        return None


def _try_load_ddddocr():
    """尝试加载 ddddocr（轻量级，主要用于验证码，英文效果一般）"""
    try:
        import ddddocr
        ocr = ddddocr.DdddOcr(show_ad=False)
        return ('ddddocr', ocr)
    except Exception:
        return None


_OCR_ENGINE = None

def get_ocr_engine():
    """按优先级获取可用 OCR 引擎（懒加载，只初始化一次）"""
    global _OCR_ENGINE
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE

    for loader in [_try_load_paddleocr, _try_load_easyocr,
                   _try_load_pytesseract, _try_load_ddddocr]:
        result = loader()
        if result:
            _OCR_ENGINE = result
            print(f"[OCR] 使用引擎: {result[0]}")
            return _OCR_ENGINE

    print("[OCR] 警告: 未找到可用 OCR 引擎，图片识别将跳过。")
    print("      安装建议: pip install easyocr  或  pip install paddleocr paddlepaddle")
    _OCR_ENGINE = (None, None)
    return _OCR_ENGINE


def ocr_image_bytes(img_bytes):
    """
    对图片字节数据执行 OCR，返回识别出的文本字符串。
    失败时返回空字符串。
    """
    engine_name, engine = get_ocr_engine()
    if not engine_name:
        return ''

    try:
        if engine_name == 'paddleocr':
            import numpy as np
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            img_np = np.array(img)
            result = engine.ocr(img_np, cls=True)
            if result and result[0]:
                lines = [item[1][0] for line in result for item in line if item]
                return '\n'.join(lines)

        elif engine_name == 'easyocr':
            import numpy as np
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            img_np = np.array(img)
            result = engine.readtext(img_np, detail=0)
            return '\n'.join(result)

        elif engine_name == 'tesseract':
            from PIL import Image
            import pytesseract
            img = Image.open(io.BytesIO(img_bytes))
            # 同时尝试中文和英文
            text = pytesseract.image_to_string(img, lang='eng+chi_sim',
                                               config='--psm 6')
            return text

        elif engine_name == 'ddddocr':
            return engine.classification(img_bytes)

    except Exception as e:
        print(f"[OCR] 识别失败: {e}")

    return ''


# ─────────────────────────── 图片提取 ───────────────────────────

# 微信图片 URL 特征：
#   https://mmbiz.qpic.cn/...  或  https://mmbiz.qlogo.cn/...
WECHAT_IMG_PATTERN = re.compile(
    r'(?:src|data-src)["\s]*=["\s]*'
    r'(https?://(?:mmbiz\.qpic\.cn|mmbiz\.qlogo\.cn|res\.wx\.qq\.com)'
    r'[^"\'>\s]+)',
    re.IGNORECASE
)

# 通用 img src（兜底，排除 base64/svg/icon）
GENERIC_IMG_PATTERN = re.compile(
    r'<img[^>]+(?:data-src|src)\s*=\s*["\']'
    r'(https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\'>\s]*)?)'
    r'["\']',
    re.IGNORECASE
)


def extract_image_urls(html):
    """从公众号 HTML 中提取所有图片 URL（优先 data-src，过滤图标/表情）"""
    urls = []
    seen = set()

    # 先匹配微信 CDN 图片（精度高）
    for m in WECHAT_IMG_PATTERN.finditer(html):
        url = m.group(1).strip()
        # 去掉尾部多余字符
        url = re.split(r'[\s"\'<>]', url)[0]
        if url not in seen:
            seen.add(url)
            urls.append(url)

    # 再匹配通用图片（去重）
    for m in GENERIC_IMG_PATTERN.finditer(html):
        url = m.group(1).strip()
        if url not in seen:
            seen.add(url)
            urls.append(url)

    # 过滤掉明显不含内容的小图（表情包/图标往往 URL 包含 emoji / icon 关键词）
    filtered = []
    skip_keywords = ['emoji', 'icon', 'logo', 'avatar', 'qrcode', 'ad_', 'gif']
    for url in urls:
        url_lower = url.lower()
        if not any(k in url_lower for k in skip_keywords):
            filtered.append(url)

    return filtered


def download_image(url, timeout=15):
    """下载单张图片，返回字节数据，失败返回 None"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://mp.weixin.qq.com/'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200 and len(resp.content) > 1024:  # 过滤 <1KB 的占位图
            return resp.content
    except Exception as e:
        pass
    return None


def is_likely_title_image(img_bytes):
    """
    简单启发式判断：图片是否可能包含标题文字
    - 排除宽高比极端的图片（头像/小图标）
    - 排除文件过小的图片
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        # 宽度 > 300px，且宽高比在 1:10 ~ 10:1 之间
        if w < 300:
            return False
        ratio = w / h if h > 0 else 0
        if ratio < 0.1 or ratio > 15:
            return False
        return True
    except Exception:
        # 无法用 PIL 判断，直接放行
        return True


def ocr_article_images(html, max_images=20, verbose=False):
    """
    提取文章中图片并 OCR，返回所有识别到的文本拼接字符串。
    
    max_images: 最多处理图片数量（避免耗时过长）
    """
    engine_name, _ = get_ocr_engine()
    if not engine_name:
        return ''

    img_urls = extract_image_urls(html)
    if not img_urls:
        return ''

    if verbose:
        print(f"[OCR] 发现 {len(img_urls)} 张图片，将处理前 {min(len(img_urls), max_images)} 张")

    all_text = []
    processed = 0

    for url in img_urls[:max_images]:
        img_bytes = download_image(url)
        if not img_bytes:
            continue

        if not is_likely_title_image(img_bytes):
            if verbose:
                print(f"[OCR] 跳过小图: {url[:60]}...")
            continue

        if verbose:
            print(f"[OCR] 识别: {url[:60]}...")

        text = ocr_image_bytes(img_bytes)
        if text and text.strip():
            all_text.append(text.strip())
            processed += 1
            if verbose:
                preview = text.strip().replace('\n', ' ')[:100]
                print(f"[OCR]   → {preview}")

    if verbose and processed > 0:
        print(f"[OCR] 共从 {processed} 张图片中提取到文字")

    return '\n'.join(all_text)


# ─────────────────────────── 文章抓取 ───────────────────────────

def extract_wechat_article_content(url):
    """提取公众号文章 HTML 内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://mp.weixin.qq.com/'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        return response.text
    except Exception as e:
        print(f"获取文章内容失败: {e}")
        return None


# ─────────────────────────── 文本提取 ───────────────────────────

def extract_dois(text):
    """从文本中提取 DOI"""
    doi_patterns = [
        r'10\.\d{4,}\/[^\s"<>]+',
        r'DOI[:\s]*10\.\d{4,}\/[^\s"<>]+',
        r'doi[:\s]*10\.\d{4,}\/[^\s"<>]+',
        r'https?://doi\.org/10\.\d{4,}\/[^\s"<>]+',
        r'https?://dx\.doi\.org/10\.\d{4,}\/[^\s"<>]+',
    ]
    dois = []
    for pattern in doi_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            doi = match
            if 'doi.org/' in match.lower():
                doi = match.split('doi.org/')[-1]
            elif 'dx.doi.org/' in match.lower():
                doi = match.split('dx.doi.org/')[-1]
            else:
                doi = re.sub(r'^[Dd][Oo][Ii][:\s]*', '', match)
            doi = doi.strip('.,;:"\'')
            if doi.startswith('10.') and doi not in dois:
                dois.append(doi)
    return dois


def extract_paper_titles(text):
    """从文本中提取可能的论文标题"""
    titles = []
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = unescape(clean_text)

    # 模式1: 引号中的长文本
    quote_patterns = [
        r'"([^"]{30,200})"',
        r'"([^"]{30,200})"',
        r'《([^》]{10,100})》',
    ]
    for pattern in quote_patterns:
        matches = re.findall(pattern, clean_text)
        for match in matches:
            match = match.strip()
            if 20 < len(match) < 200 and not any(
                x in match.lower() for x in ['http', 'www', '.com', 'click', '订阅']
            ):
                if match not in titles:
                    titles.append(match)

    # 模式2: 以特定关键词开头的句子
    title_indicators = [
        r'(?:标题|题目|Title)[:：]\s*([^\n。]{20,150})',
        r'(?:研究|论文|文章)[:：]\s*["「『《]?([^\n"」』》]{20,150})',
        r'(?:published|titled|entitled)[:\s]+["\']?([^"\']{20,150})',
    ]
    for pattern in title_indicators:
        matches = re.findall(pattern, clean_text, re.IGNORECASE)
        for match in matches:
            match = match.strip()
            if 20 < len(match) < 200 and match not in titles:
                titles.append(match)

    # 模式3: 学术标题结构（英文）
    academic_pattern = r'([A-Z][^。！？\n]{30,150}(?:in|of|for|on|and|the)[^。！？\n]{10,100})'
    matches = re.findall(academic_pattern, clean_text)
    for match in matches:
        match = match.strip()
        if 30 < len(match) < 200 and match not in titles:
            academic_keywords = [
                'study', 'analysis', 'effect', 'impact', 'association',
                'risk', 'patients', 'treatment', 'clinical', 'research'
            ]
            if any(kw in match.lower() for kw in academic_keywords):
                titles.append(match)

    titles.sort(key=lambda x: abs(len(x) - 80))
    return titles[:5]


def extract_journal_info(text):
    """提取期刊名称和发表信息"""
    journal_patterns = [
        r'(?:发表于|Published in|journal)[:\s]+([A-Z][a-zA-Z\s]{5,50})',
        r'([A-Z][a-zA-Z\s]{5,30}Journal[A-Za-z\s]{0,20})',
        r'([A-Z][a-zA-Z\s]{5,30}Medicine[A-Za-z\s]{0,20})',
        r'([A-Z][a-zA-Z\s]{5,30}Research[A-Za-z\s]{0,20})',
    ]
    journals = []
    for pattern in journal_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            match = match.strip()
            if len(match) > 5 and match not in journals:
                journals.append(match)
    return journals[:3]


# ─────────────────────────── 主解析入口 ───────────────────────────

def parse_wechat_article(url, enable_ocr=True, verbose=False):
    """
    解析公众号文章，提取科研文献信息。

    Parameters
    ----------
    url        : 公众号文章链接
    enable_ocr : 是否对正文图片执行 OCR 识别（默认 True）
    verbose    : 是否打印 OCR 详细进度

    Returns
    -------
    dict with keys: url, dois, titles, journals,
                    ocr_text (图片 OCR 原始文本),
                    ocr_dois, ocr_titles (从图片中额外提取的结果)
    """
    print(f"正在解析文章: {url}")
    print("-" * 50)

    html_content = extract_wechat_article_content(url)
    if not html_content:
        return None

    # 1. 从 HTML 文本中提取
    dois   = extract_dois(html_content)
    titles = extract_paper_titles(html_content)
    journals = extract_journal_info(html_content)

    # 2. 从图片 OCR 中提取（补充识别正文中以图片形式呈现的标题）
    ocr_text  = ''
    ocr_dois  = []
    ocr_titles = []

    if enable_ocr:
        print("\n[OCR] 开始识别正文图片...")
        ocr_text = ocr_article_images(html_content, verbose=verbose)
        if ocr_text:
            ocr_dois   = [d for d in extract_dois(ocr_text) if d not in dois]
            ocr_titles = [t for t in extract_paper_titles(ocr_text)
                          if t not in titles]
            # 合并到主结果（OCR 结果排在后面）
            dois   = dois   + ocr_dois
            titles = titles + ocr_titles
        else:
            print("[OCR] 未从图片中提取到有效文字")

    result = {
        'url': url,
        'dois': dois,
        'titles': titles,
        'journals': journals,
        'ocr_text': ocr_text,
        'ocr_dois': ocr_dois,
        'ocr_titles': ocr_titles,
    }
    return result


# ─────────────────────────── 输出展示 ───────────────────────────

def display_results(result):
    """显示解析结果"""
    if not result:
        print("未能解析到任何信息")
        return

    print("\n解析结果:")
    print("=" * 50)

    if result['dois']:
        print(f"\n找到 {len(result['dois'])} 个DOI:")
        for i, doi in enumerate(result['dois'], 1):
            src = ' [图片OCR]' if doi in result.get('ocr_dois', []) else ''
            print(f"  {i}. {doi}{src}")
    else:
        print("\n未找到DOI")

    if result['titles']:
        print(f"\n找到 {len(result['titles'])} 个可能的标题:")
        for i, title in enumerate(result['titles'], 1):
            src = ' [图片OCR]' if title in result.get('ocr_titles', []) else ''
            print(f"  {i}. {title}{src}")
    else:
        print("\n未找到标题")

    if result['journals']:
        print(f"\n找到 {len(result['journals'])} 个期刊信息:")
        for i, journal in enumerate(result['journals'], 1):
            print(f"  {i}. {journal}")

    print("=" * 50)


# ─────────────────────────── HNLAT 提交 ───────────────────────────

def submit_to_hnlat(identifier, is_doi=True):
    """调用 hnlat_auto.py 提交文献"""
    import subprocess

    if is_doi:
        cmd = [sys.executable, "hnlat_auto.py", "--doi", identifier]
    else:
        cmd = [sys.executable, "hnlat_auto.py", "--title", identifier]

    print(f"\n正在提交到 HNLAT: {identifier}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("错误:", result.stderr)
    return result.returncode == 0


# ─────────────────────────── CLI 入口 ───────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="微信公众号文章科研文献解析工具（支持图片 OCR）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "https://mp.weixin.qq.com/s/xxxxx"          解析文章（自动 OCR 图片）
  %(prog)s "URL" --no-ocr                               跳过图片 OCR
  %(prog)s "URL" --submit                               解析并自动提交
  %(prog)s "URL" --verbose                              显示 OCR 详细进度
        """,
    )
    parser.add_argument("url", help="公众号文章URL")
    parser.add_argument("--submit",   action="store_true", help="解析后自动提交到HNLAT")
    parser.add_argument("--no-ocr",   action="store_true", help="禁用图片OCR识别")
    parser.add_argument("--verbose",  action="store_true", help="显示OCR详细进度")
    args = parser.parse_args()

    enable_ocr = not args.no_ocr

    # 解析文章
    result = parse_wechat_article(args.url, enable_ocr=enable_ocr,
                                  verbose=args.verbose)

    # 显示结果
    display_results(result)

    # 自动提交
    if args.submit and result:
        if result['dois']:
            for doi in result['dois']:
                submit_to_hnlat(doi, is_doi=True)
        elif result['titles']:
            submit_to_hnlat(result['titles'][0], is_doi=False)
        else:
            print("\n未能提取到DOI或标题，无法提交")
    elif result and (result['dois'] or result['titles']):
        print("\n提示: 使用 --submit 参数可自动提交到HNLAT")


if __name__ == '__main__':
    main()
