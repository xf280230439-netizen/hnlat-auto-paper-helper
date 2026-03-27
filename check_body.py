import sys
sys.path.insert(0, '.')
from hnlat_auto import load_config, HNLATBot
from datetime import datetime, timedelta
import imaplib
import email as email_lib
import re

config = load_config()
bot = HNLATBot(config)

# 连接邮箱
mail = imaplib.IMAP4_SSL('imap.qq.com', 993)
mail.login(config['qq_email'], config['qq_imap_auth'])
mail.select('INBOX')

# 搜索最近7天所有邮件
since = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
st, msgs = mail.search(None, f'SINCE {since}')

# 检查最新一封HNLAT邮件的正文
for eid in list(reversed(msgs[0].split()))[:3]:
    _, raw = mail.fetch(eid, '(RFC822)')
    msg = email_lib.message_from_bytes(raw[0][1])
    subj = bot._decode_header(msg.get('Subject', ''))
    
    if '文献互助' not in subj:
        continue
    
    print(f'=== {subj} ===')
    print(f'Date: {msg.get("Date", "")}')
    
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
    
    # 查找下载链接
    links = re.findall(r'https?://[^\s<>"]+\.pdf[^\s<>"]*', body)
    links += re.findall(r'https?://paper\.hnlat\.com[^\s<>"]*', body)
    
    print(f'正文长度: {len(body)} 字符')
    if links:
        print(f'找到链接: {links}')
    else:
        print('正文前500字符:')
        print(body[:500])
    print()

mail.logout()
