#!/usr/bin/env python3
"""
HNLAT 文献下载 - 一键完整流程

整合流程：
1. 监控邮箱获取新下载链接
2. 使用 Playwright 自动下载 PDF
3. 自动分类整理文献

用法：
    python auto_download_flow.py
    python auto_download_flow.py --organize  # 下载后自动分类
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import imaplib
import email as email_lib
import re
import shutil

sys.path.insert(0, str(Path(__file__).parent))
from hnlat_auto import load_config, HNLATBot
from playwright.async_api import async_playwright

# Windows UTF-8 兼容
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

config = load_config()
download_dir = Path(__file__).parent / 'downloads'
download_dir.mkdir(exist_ok=True)


def get_new_download_links():
    """从邮箱提取新的下载链接"""
    bot = HNLATBot(config)
    
    # 已下载的文件
    existing = set()
    for pdf in download_dir.rglob('*.pdf'):
        existing.add(pdf.stem.lower()[:30])
    
    # 连接邮箱
    mail = imaplib.IMAP4_SSL('imap.qq.com', 993)
    mail.login(config['qq_email'], config['qq_imap_auth'])
    mail.select('INBOX')
    
    since = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
    st, msgs = mail.search(None, f'SINCE {since}')
    
    new_links = []
    for eid in reversed(msgs[0].split()):
        _, raw = mail.fetch(eid, '(RFC822)')
        msg = email_lib.message_from_bytes(raw[0][1])
        subj = bot._decode_header(msg.get('Subject', ''))
        
        if '文献互助' not in subj:
            continue
        
        # 获取正文
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                elif part.get_content_type() == 'text/html' and not body:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        # 提取标题和链接
        title_match = re.search(r'文献互助•成功\]-([^\n<]+)', subj)
        title = title_match.group(1).strip()[:50] if title_match else 'unknown'
        
        links = re.findall(r'https://mail-ddp-sc102\.huicece\.com/delivery-give\?_hri=(\d+)&_gri=(\d+)&c=([A-F0-9]+)', body)
        if not links:
            links = re.findall(r'https://mail-ddp-sc102\.huicece\.com/delivery-give\?_hri=(\d+)_gri=(\d+)&c=([A-F0-9]+)', body)
        
        if links:
            hri, gri, c = links[0]
            link = f'https://mail-ddp-sc102.huicece.com/delivery-give?_hri={hri}&_gri={gri}&c={c}'
            
            # 检查是否已下载
            title_key = title.lower()[:30]
            if title_key not in existing:
                new_links.append((title, link))
    
    mail.logout()
    return new_links


async def download_with_playwright(links):
    """使用 Playwright 下载 PDF"""
    print(f'\n启动浏览器下载 {len(links)} 篇文献...\n')
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        
        downloaded = []
        for i, (title, url) in enumerate(links, 1):
            print(f'[{i}/{len(links)}] {title[:40]}...')
            
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(3000)
                
                download_btn = await page.query_selector('a:has-text("下载")')
                
                if download_btn:
                    async with page.expect_download(timeout=60000) as dl_info:
                        await download_btn.click()
                        download = await dl_info.value
                        
                        safe_title = title.replace('/', '_').replace('\\', '_').replace(':', '_')[:50]
                        filename = f"{safe_title}.pdf"
                        filepath = download_dir / filename
                        await download.save_as(filepath)
                        print(f'  ✓ 已下载: {filename}')
                        downloaded.append(filename)
                else:
                    print(f'  ✗ 未找到下载按钮')
                        
            except Exception as e:
                print(f'  ✗ 错误: {e}')
        
        await browser.close()
        return downloaded


def organize_pdfs():
    """分类整理 PDF"""
    categories = {
        "01_肠道菌群与代谢": ["gut", "microbiota", "microbiome", "scfa", "fatty acid", "roseburia"],
        "02_肠-肝轴与肠道干细胞": ["gut-liver", "liver", "stem cell", "intestinal"],
        "03_肠-皮轴与皮肤健康": ["gut-skin", "dermal", "skin"],
        "04_衰老与抗衰老机制": ["ageing", "aging", "lithocholic", "calorie restriction"],
        "05_肿瘤免疫": ["tumor", "cancer", "immune", "telomere", "t cell"],
        "06_微生物群落生态": ["predator", "community", "divergence", "convergence"],
        "07_人工智能与微生物组": ["machine learning", "ai", "prediction", "consortia"],
        "08_大型队列与精准医学": ["phenotype", "cohort", "population"],
        "09_G蛋白偶联受体": ["gpr", "gpcr", "receptor", "proton sensing"],
    }
    
    print('\n整理文献分类...')
    
    for pdf in download_dir.glob('*.pdf'):
        name_lower = pdf.stem.lower()
        
        matched = False
        for category, keywords in categories.items():
            if any(kw in name_lower for kw in keywords):
                cat_dir = download_dir / category
                cat_dir.mkdir(exist_ok=True)
                shutil.move(str(pdf), str(cat_dir / pdf.name))
                print(f'  {pdf.name} -> {category}/')
                matched = True
                break
        
        if not matched:
            other_dir = download_dir / "10_其他"
            other_dir.mkdir(exist_ok=True)
            shutil.move(str(pdf), str(other_dir / pdf.name))
            print(f'  {pdf.name} -> 10_其他/')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='HNLAT 文献下载一键流程')
    parser.add_argument('--organize', action='store_true', help='下载后自动分类')
    args = parser.parse_args()
    
    print('='*50)
    print('HNLAT 文献下载一键流程')
    print('='*50)
    
    # 1. 检查新链接
    print('\n[1/3] 检查邮箱获取新下载链接...')
    new_links = get_new_download_links()
    
    if not new_links:
        print('没有需要下载的新文献')
        return
    
    print(f'发现 {len(new_links)} 篇新文献待下载')
    
    # 2. 下载
    print('\n[2/3] 下载 PDF...')
    downloaded = asyncio.run(download_with_playwright(new_links))
    print(f'\n成功下载 {len(downloaded)} 篇文献')
    
    # 3. 分类
    if args.organize:
        print('\n[3/3] 分类整理...')
        organize_pdfs()
    
    print('\n' + '='*50)
    print('完成！')
    print(f'下载目录: {download_dir}')
    print('='*50)


if __name__ == '__main__':
    main()
