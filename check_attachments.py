import sys
sys.path.insert(0, '.')
from hnlat_auto import load_config, HNLATBot
from datetime import datetime, timedelta
import imaplib
import email as email_lib
import os

config = load_config()
bot = HNLATBot(config)

# 连接邮箱
mail = imaplib.IMAP4_SSL('imap.qq.com', 993)
mail.login(config['qq_email'], config['qq_imap_auth'])
mail.select('INBOX')

# 搜索最近7天所有邮件
since = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
st, msgs = mail.search(None, f'SINCE {since}')
print(f'搜索到 {len(msgs[0].split())} 封邮件\n')

# 检查每封邮件的附件
pdf_count = 0
for eid in reversed(msgs[0].split()):
    _, raw = mail.fetch(eid, '(RFC822)')
    msg = email_lib.message_from_bytes(raw[0][1])
    subj = bot._decode_header(msg.get('Subject', ''))
    
    # 检查附件
    attachments = []
    for part in msg.walk():
        if part.get_content_disposition() == 'attachment':
            fn = bot._decode_header(part.get_filename() or '')
            if fn:
                attachments.append(fn)
                if fn.lower().endswith('.pdf'):
                    pdf_count += 1
    
    if '文献互助' in subj or 'HNLAT' in subj.lower() or attachments:
        print(f'[{msg.get("Date", "")[:30]}] {subj[:60]}')
        if attachments:
            print(f'  📎 附件: {attachments}')

mail.logout()
print(f'\n共找到 {pdf_count} 个 PDF 附件')
