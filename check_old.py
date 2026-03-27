import sys, imaplib, email as email_lib
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from hnlat_auto import HNLATBot, load_config

config = load_config()
helper = HNLATBot(config)
mail = helper._imap_connect()

# 搜索最近365天所有来自hnlat的邮件
since = (datetime.now() - timedelta(days=365)).strftime('%d-%b-%Y')
queries = [
    f'(FROM "hnlat" SINCE {since})',
    f'(SUBJECT "paper" SINCE {since})',
]

all_emails = []
seen_ids = set()
for q in queries:
    st, msgs = mail.search(None, q)
    if not msgs[0]: continue
    for eid in msgs[0].split():
        eid_str = eid.decode()
        if eid_str in seen_ids: continue
        seen_ids.add(eid_str)
        _, raw = mail.fetch(eid, '(RFC822)')
        msg = email_lib.message_from_bytes(raw[0][1])
        subj = helper._decode_header(msg.get('Subject', ''))
        has_pdf = False
        attachments = []
        for p in msg.walk():
            if p.get_content_disposition() == 'attachment':
                fn = helper._decode_header(p.get_filename() or '')
                if fn.lower().endswith('.pdf'):
                    has_pdf = True
                    attachments.append(fn)
        all_emails.append({'id': eid_str, 'subject': subj, 'date': msg.get('Date', ''), 'has_pdf': has_pdf, 'attachments': attachments})

mail.logout()

print(f'共找到 {len(all_emails)} 封邮件，其中 {sum(1 for e in all_emails if e["has_pdf"])} 封含 PDF')
for e in all_emails:
    atts = ', '.join(e['attachments']) if e['attachments'] else ''
    print(f'  [{e["date"]}] {"📄" if e["has_pdf"] else "📭"} {e["subject"]}')
    if atts:
        print(f'    附件: {atts}')
