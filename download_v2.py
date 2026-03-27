import sys
sys.path.insert(0, '.')
from hnlat_auto import load_config, HNLATBot
from datetime import datetime, timedelta
import imaplib
import email as email_lib
import re
import requests
import os
from pathlib import Path
import time

config = load_config()
bot = HNLATBot(config)
download_dir = Path(__file__).parent / 'downloads'
download_dir.mkdir(exist_ok=True)

# 创建 session 模拟浏览器
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
})

# 连接邮箱
mail = imaplib.IMAP4_SSL('imap.qq.com', 993)
mail.login(config['qq_email'], config['qq_imap_auth'])
mail.select('INBOX')

# 搜索最近7天所有邮件
since = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
st, msgs = mail.search(None, f'SINCE {since}')

print('提取下载链接并尝试下载...\n')

downloaded = []
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
    
    # 提取下载链接
    links = re.findall(r'https://mail-ddp-sc102\.huicece\.com/delivery-give\?_hri=(\d+)&_gri=(\d+)&c=([A-F0-9]+)', body)
    if not links:
        links = re.findall(r'https://mail-ddp-sc102\.huicece\.com/delivery-give\?_hri=(\d+)_gri=(\d+)&c=([A-F0-9]+)', body)
    
    if links:
        hri, gri, c = links[0]
        link = f'https://mail-ddp-sc102.huicece.com/delivery-give?_hri={hri}&_gri={gri}&c={c}'
        
        # 提取标题
        title_match = re.search(r'文献互助•成功\]-([^\n<]+)', subj)
        title = title_match.group(1).strip() if title_match else f'paper_{len(downloaded)+1}'
        title = title[:80].replace('/', '_').replace('\\', '_').replace(':', '_').replace('"', '')
        
        print(f'📥 [{len(downloaded)+1}] {title[:50]}...')
        
        try:
            # 先访问页面获取 cookies
            resp1 = session.get(link, timeout=30, allow_redirects=True)
            print(f'   页面状态: {resp1.status_code}, URL: {resp1.url}')
            
            # 尝试直接请求 PDF
            pdf_url = f'https://mail-ddp-sc102.huicece.com/delivery-download?_hri={hri}&_gri={gri}&c={c}'
            resp2 = session.get(pdf_url, timeout=60, allow_redirects=True)
            
            content_type = resp2.headers.get('Content-Type', '')
            print(f'   PDF状态: {resp2.status_code}, Content-Type: {content_type}')
            
            if resp2.status_code == 200 and ('pdf' in content_type.lower() or len(resp2.content) > 10000):
                filename = f'{title}.pdf'
                filepath = download_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(resp2.content)
                print(f'   ✅ 已保存: {filename} ({len(resp2.content)} bytes)')
                downloaded.append(filename)
            else:
                # 检查响应内容
                if b'%PDF' in resp2.content[:100]:
                    filename = f'{title}.pdf'
                    filepath = download_dir / filename
                    with open(filepath, 'wb') as f:
                        f.write(resp2.content)
                    print(f'   ✅ 已保存: {filename} ({len(resp2.content)} bytes)')
                    downloaded.append(filename)
                else:
                    print(f'   ❌ 非 PDF 内容')
                    
        except Exception as e:
            print(f'   ❌ 错误: {e}')
        
        time.sleep(1)  # 避免请求过快

mail.logout()
print(f'\n✅ 共下载 {len(downloaded)} 个 PDF 到 downloads/ 目录')
for f in downloaded:
    print(f'   - {f}')
