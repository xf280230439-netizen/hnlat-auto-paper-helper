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

config = load_config()
bot = HNLATBot(config)
download_dir = Path(__file__).parent / 'downloads'
download_dir.mkdir(exist_ok=True)

# 连接邮箱
mail = imaplib.IMAP4_SSL('imap.qq.com', 993)
mail.login(config['qq_email'], config['qq_imap_auth'])
mail.select('INBOX')

# 搜索最近7天所有邮件
since = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
st, msgs = mail.search(None, f'SINCE {since}')

print('提取下载链接并下载 PDF...\n')

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
    links = re.findall(r'https://mail-ddp-sc102\.huicece\.com/delivery-give\?_hri=\d+_gri=\d+&c=[A-F0-9]+', body)
    if not links:
        links = re.findall(r'https://mail-ddp-sc102\.huicece\.com/delivery-give\?_hri=\d+&_gri=\d+&c=[A-F0-9]+', body)
    
    if links:
        link = links[0]
        # 提取标题
        title_match = re.search(r'文献互助•成功\]-([^\n<]+)', subj)
        title = title_match.group(1).strip() if title_match else f'paper_{len(downloaded)+1}'
        title = title[:80]  # 截断过长的标题
        
        print(f'📥 下载: {title[:50]}...')
        print(f'   链接: {link[:60]}...')
        
        try:
            resp = requests.get(link, timeout=30, allow_redirects=True)
            if resp.status_code == 200 and 'application/pdf' in resp.headers.get('Content-Type', ''):
                filename = title.replace('/', '_').replace('\\', '_').replace(':', '_') + '.pdf'
                filepath = download_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                print(f'   ✅ 已保存: {filename} ({len(resp.content)} bytes)')
                downloaded.append(filename)
            else:
                print(f'   ❌ 下载失败: status={resp.status_code}, type={resp.headers.get("Content-Type", "")}')
        except Exception as e:
            print(f'   ❌ 错误: {e}')

mail.logout()
print(f'\n共下载 {len(downloaded)} 个 PDF 到 downloads/ 目录')
