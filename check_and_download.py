import sys
sys.path.insert(0, '.')
from hnlat_auto import load_config, HNLATBot
from datetime import datetime, timedelta
import imaplib
import email as email_lib
import re
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

config = load_config()
bot = HNLATBot(config)
download_dir = Path(__file__).parent / 'downloads'

# 已下载的文件名
existing_pdfs = set()
for pdf in download_dir.rglob('*.pdf'):
    existing_pdfs.add(pdf.name.lower())

# 连接邮箱
mail = imaplib.IMAP4_SSL('imap.qq.com', 993)
mail.login(config['qq_email'], config['qq_imap_auth'])
mail.select('INBOX')

# 搜索最近7天所有邮件
since = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
st, msgs = mail.search(None, f'SINCE {since}')

print('检查新文献...\n')

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
    title = title_match.group(1).strip()[:60] if title_match else 'unknown'
    
    # 提取下载链接
    links = re.findall(r'https://mail-ddp-sc102\.huicece\.com/delivery-give\?_hri=(\d+)&_gri=(\d+)&c=([A-F0-9]+)', body)
    if not links:
        links = re.findall(r'https://mail-ddp-sc102\.huicece\.com/delivery-give\?_hri=(\d+)_gri=(\d+)&c=([A-F0-9]+)', body)
    
    if links:
        hri, gri, c = links[0]
        link = f'https://mail-ddp-sc102.huicece.com/delivery-give?_hri={hri}&_gri={gri}&c={c}'
        
        # 检查是否已下载（通过标题关键词）
        title_key = title.lower().split()[0] if title else ''
        already_exists = any(title_key in pdf_name for pdf_name in existing_pdfs)
        
        if not already_exists:
            new_links.append((title, link))
            print(f'新文献: {title}')

mail.logout()

if not new_links:
    print('没有需要下载的新文献')
else:
    print(f'\n共 {len(new_links)} 篇新文献待下载')
    
    # 使用 Playwright 下载
    async def download_new():
        print('\n启动浏览器下载...')
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            
            for i, (title, url) in enumerate(new_links, 1):
                print(f'\n[{i}/{len(new_links)}] {title[:40]}...')
                
                try:
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(3000)
                    
                    download_btn = await page.query_selector('a:has-text("下载")')
                    
                    if download_btn:
                        async with page.expect_download(timeout=60000) as download_info:
                            await download_btn.click()
                            download = await download_info.value
                            
                            safe_title = title.replace('/', '_').replace('\\', '_').replace(':', '_')[:50]
                            filename = f"{safe_title}.pdf"
                            filepath = download_dir / filename
                            await download.save_as(filepath)
                            print(f'  SUCCESS: {filename}')
                    else:
                        print(f'  未找到下载按钮')
                            
                except Exception as e:
                    print(f'  ERROR: {e}')
            
            await browser.close()
            print('\n下载完成！')
    
    asyncio.run(download_new())
