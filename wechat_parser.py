#!/usr/bin/env python3
"""
微信公众号文章科研文献自动解析工具

功能：
1. 解析公众号文章链接，提取其中提到的科研文献信息（DOI或标题）
2. 自动调用 hnlat_auto.py 提交并下载文献

使用方法：
python wechat_parser.py <公众号文章URL>
python wechat_parser.py --api  # 启动API服务
"""

import argparse
import re
import json
import requests
import sys
from urllib.parse import urlparse
from html import unescape
from pathlib import Path


def extract_wechat_article_content(url):
    """
    提取公众号文章内容
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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


def extract_dois(text):
    """
    从文本中提取DOI
    """
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
    """
    从文本中提取可能的论文标题
    """
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
            if 20 < len(match) < 200 and not any(x in match.lower() for x in ['http', 'www', '.com', 'click', '订阅']):
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
    
    # 模式3: 学术标题结构
    academic_pattern = r'([A-Z][^。！？\n]{30,150}(?:in|of|for|on|and|the)[^。！？\n]{10,100})'
    matches = re.findall(academic_pattern, clean_text)
    for match in matches:
        match = match.strip()
        if 30 < len(match) < 200 and match not in titles:
            academic_keywords = ['study', 'analysis', 'effect', 'impact', 'association', 'risk', 'patients', 'treatment', 'clinical', 'research']
            if any(kw in match.lower() for kw in academic_keywords):
                titles.append(match)
    
    titles.sort(key=lambda x: abs(len(x) - 80))
    return titles[:5]


def extract_journal_info(text):
    """
    提取期刊名称和发表信息
    """
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


def parse_wechat_article(url):
    """
    解析公众号文章，提取科研文献信息
    """
    print(f"正在解析文章: {url}")
    print("-" * 50)
    
    html_content = extract_wechat_article_content(url)
    if not html_content:
        return None
    
    dois = extract_dois(html_content)
    titles = extract_paper_titles(html_content)
    journals = extract_journal_info(html_content)
    
    result = {
        'url': url,
        'dois': dois,
        'titles': titles,
        'journals': journals
    }
    
    return result


def display_results(result):
    """
    显示解析结果
    """
    if not result:
        print("未能解析到任何信息")
        return
    
    print("\n解析结果:")
    print("=" * 50)
    
    if result['dois']:
        print(f"\n找到 {len(result['dois'])} 个DOI:")
        for i, doi in enumerate(result['dois'], 1):
            print(f"  {i}. {doi}")
    else:
        print("\n未找到DOI")
    
    if result['titles']:
        print(f"\n找到 {len(result['titles'])} 个可能的标题:")
        for i, title in enumerate(result['titles'], 1):
            print(f"  {i}. {title}")
    else:
        print("\n未找到标题")
    
    if result['journals']:
        print(f"\n找到 {len(result['journals'])} 个期刊信息:")
        for i, journal in enumerate(result['journals'], 1):
            print(f"  {i}. {journal}")
    
    print("=" * 50)


def submit_to_hnlat(identifier, is_doi=True):
    """
    调用 hnlat_auto.py 提交文献
    """
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


def main():
    parser = argparse.ArgumentParser(
        description="微信公众号文章科研文献解析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "https://mp.weixin.qq.com/s/xxxxx"     解析文章
  %(prog)s "URL" --submit                          解析并自动提交
        """,
    )
    parser.add_argument("url", help="公众号文章URL")
    parser.add_argument("--submit", action="store_true", help="解析后自动提交到HNLAT")
    args = parser.parse_args()
    
    # 解析文章
    result = parse_wechat_article(args.url)
    
    # 显示结果
    display_results(result)
    
    # 自动提交
    if args.submit and result:
        if result['dois']:
            for doi in result['dois']:
                submit_to_hnlat(doi, is_doi=True)
        elif result['titles']:
            # 使用第一个标题
            submit_to_hnlat(result['titles'][0], is_doi=False)
        else:
            print("\n未能提取到DOI或标题，无法提交")
    elif result and (result['dois'] or result['titles']):
        print("\n提示: 使用 --submit 参数可自动提交到HNLAT")


if __name__ == '__main__':
    main()
