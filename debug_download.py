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

print('提取下载链接...\n')

# 只处理第一封，看看返回内容
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
        # 修正链接格式
        link = link.replace('_gri=', '&_gri=')
        
        print(f'标题: {subj}')
        print(f'链接: {link}')
        
        # 使用浏览器下载
        resp = requests.get(link, timeout=30, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        print(f'Status: {resp.status_code}')
        print(f'Content-Type: {resp.headers.get("Content-Type", "")}')
        print(f'URL: {resp.url}')
        
        # 保存响应内容
        with open(download_dir / 'response.html', 'w', encoding='utf-8') as f:
            f.write(resp.text)
        print(f'响应已保存到 response.html ({len(resp.text)} 字符)')
        
        # 查找PDF链接
        pdf_links = re.findall(r'href="([^"]*\.pdf[^"]*)"', resp.text)
        print(f'找到的PDF链接: {pdf_links}')
        break

mail.logout()
