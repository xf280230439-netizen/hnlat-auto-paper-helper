#!/usr/bin/env python3
"""
=============================================================
  HNLAT 纬度文献互助平台 — 自动化工具
=============================================================

功能：
  1. 自动登录 paper.hnlat.com（通过 SSO 单点登录）
  2. 通过 DOI 或论文标题提交文献求助
  3. 通过 IMAP 监控 QQ 邮箱，自动下载 PDF 附件
  4. 支持批量提交 + 持续监控

使用前：
  1. 复制 config.example.json 为 config.json
  2. 填入你的账号信息（详见 README.md）
  3. pip install requests

命令示例：
  python hnlat_auto.py --doi 10.1038/s41586-024-08329-5
  python hnlat_auto.py --doi-list dois.txt
  python hnlat_auto.py --title "Some paper title"
  python hnlat_auto.py --monitor
  python hnlat_auto.py --download
  python hnlat_auto.py --doi LIST --loop
=============================================================
"""

import argparse
import email as email_lib
import imaplib
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# Windows 控制台 UTF-8 兼容
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ===================== 常量（不需要改）=====================
SSO_BASE = "https://sso.hnlat.com"
PAPER_BASE = "https://paper.hnlat.com"
SERVICE_URL = (
    "https://spis.hnlat.com/loginCenter"
    "?sourceurl=https%3A%2F%2Fpaper.hnlat.com%2F"
)
IMAP_SERVER = "imap.qq.com"
IMAP_PORT = 993


def load_config() -> dict:
    """加载 config.json，缺失时给出提示并退出。"""
    script_dir = Path(__file__).parent
    config_path = script_dir / "config.json"

    if not config_path.exists():
        example_path = script_dir / "config.example.json"
        print("=" * 55)
        print("  未找到 config.json！")
        print("  请复制 config.example.json 为 config.json，")
        print("  并填入你的账号信息后再运行。")
        print("=" * 55)
        if example_path.exists():
            print(f"\n模板文件位置: {example_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))

    # 校验必填字段
    required = ["hnlat_username", "hnlat_password", "qq_email", "qq_imap_auth"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        print(f"config.json 中以下字段为空，请填写: {', '.join(missing)}")
        sys.exit(1)

    return config


# ===================== 核心类 =====================

class HNLATBot:
    """纬度文献互助平台自动化客户端。"""

    def __init__(self, config: dict):
        self.username = config["hnlat_username"]
        self.password = config["hnlat_password"]
        self.helper_email = config["qq_email"]
        self.imap_auth = config["qq_imap_auth"]
        self.download_dir = Path(config.get("download_dir", "./downloads"))
        self.loop_interval = config.get("loop_interval_seconds", 300)

        self.session = requests.Session()
        self.session.verify = False
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/132.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        })
        self.logged_in = False

    # ---------- SSO 登录 ----------

    def login(self) -> bool:
        """
        通过 HNLAT SSO 系统登录 paper.hnlat.com。

        流程：
          1. GET SSO 登录页 → 获取会话 cookie
          2. POST /login/username → 用账号密码换取 SSO ticket
          3. GET paper.hnlat.com/loginCenter → SSO 回调，建立 paper 站点会话
          4. 调用 helpTotal API 验证登录态是否有效
        """
        print("[登录] 正在通过 SSO 登录...")

        # Step 1: 获取 SSO 会话
        r = self.session.get(
            f"{SSO_BASE}/login",
            params={"service": SERVICE_URL},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  无法访问登录页 (HTTP {r.status_code})")
            return False

        # Step 2: 提交账号密码
        r = self.session.post(
            f"{SSO_BASE}/login/username",
            data={
                "un": self.username,
                "pw": self.password,
                "service": SERVICE_URL,
                "loginType": "1",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SSO_BASE,
                "Referer": (
                    f"{SSO_BASE}/login?service="
                    + urllib.parse.quote(SERVICE_URL, safe="")
                ),
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30,
        )

        data = r.json()
        if data.get("status") != 1:
            print(f"  登录失败: {data.get('message', '未知错误')}")
            return False

        print("  SSO 认证成功")

        # Step 3: SSO 回调到 paper.hnlat.com
        self.session.get(SERVICE_URL, timeout=30, allow_redirects=True)

        # Step 4: 验证
        r = self.session.get(
            f"{PAPER_BASE}/paper/tj/helpTotal",
            params={"email": self.helper_email, "username": ""},
            timeout=30,
        )
        v = r.json()
        if v.get("status") != 1:
            print(f"  会话验证失败: {v.get('message')}")
            return False

        body = v.get("body", {})
        print(f"  登录成功！今日已用 {body.get('todayTotal')} 次，"
              f"剩余 {body.get('todayRestTotal')} 次")
        self.logged_in = True
        return True

    # ---------- DOI 查询 ----------

    def lookup_doi(self, doi: str) -> dict:
        """
        通过 DOI 在 paper.hnlat.com 查询文献信息。

        API: GET /paper/findByDoiAndTitle?doi=XXX&docTitle=
        返回: {"body": {"docTitle": ..., "journalTitle": ..., "author": ..., ...}}
        """
        print(f"[查询] DOI: {doi}")
        r = self.session.get(
            f"{PAPER_BASE}/paper/findByDoiAndTitle",
            params={"doi": doi, "docTitle": ""},
            timeout=60,
        )
        data = r.json()
        body = data.get("body")
        if body:
            print(f"  找到: {body.get('docTitle')}")
            print(f"  期刊: {body.get('journalTitle', 'N/A')}"
                  f" | 年份: {body.get('year', 'N/A')}")
        else:
            print(f"  未在数据库中找到该 DOI")
        return data

    # ---------- 提交文献求助 ----------

    def submit(
        self,
        doi: str = "",
        title: str = "",
        doi_data: dict = None,
    ) -> dict:
        """
        向 paper.hnlat.com 提交文献求助请求。

        如果提供了 DOI 且未提供 doi_data，会自动先查询。
        提交成功后 PDF 会自动发送到 config 中配置的 QQ 邮箱。

        API: POST /paper/help/record
        返回状态码含义:
          status=1       → 提交成功
          status=2008    → 文献已在处理队列
          status=1001206 → 文献已被别人认领
          status=10086   → 未登录（会自动重新登录）
          status=20001   → 需要验证码/风控
        """
        # 如果有 DOI，先查询
        if doi and not doi_data:
            doi_data = self.lookup_doi(doi)

        body = (doi_data or {}).get("body")
        payload = {
            "anonymous": "false",
            "docHref": (body.get("sourceUrl") or body.get("link") or "")
            if body else "",
            "docTitle": body["docTitle"] if body else title,
            "helpChannel": 5,
            "helperEmail": self.helper_email,
            "helperName": "",
            "username": "",
            "remark": "",
            "pagesNumber": "",
            "docType": 1,
            "doi": (body.get("doi") or doi) if body else doi,
            "year": (body.get("year") or "") if body else "",
            "author": (body.get("author") or "") if body else "",
            "journal": (body.get("journalTitle") or "") if body else "",
        }
        label = doi or (title[:50] + "..." if len(title) > 50 else title)
        print(f"[提交] {label}")

        r = self.session.post(
            f"{PAPER_BASE}/paper/help/record",
            json=payload,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Origin": PAPER_BASE,
                "Referer": f"{PAPER_BASE}/",
            },
            timeout=30,
        )
        result = r.json()
        status = result.get("status")

        if status == 1:
            print(f"  提交成功！记录编号 #{result.get('body')}")
        elif status in (2008, 1001206):
            print(f"  该文献已在处理队列中 (status={status})")
        elif status == 10086:
            # 登录态失效，自动重试
            print("  登录态过期，正在重新登录...")
            if self.login():
                r2 = self.session.post(
                    f"{PAPER_BASE}/paper/help/record",
                    json=payload,
                    headers={
                        "Content-Type": "application/json;charset=UTF-8",
                        "Origin": PAPER_BASE,
                        "Referer": f"{PAPER_BASE}/",
                    },
                    timeout=30,
                )
                result = r2.json()
                if result.get("status") == 1:
                    print(f"  重新提交成功！记录 #{result.get('body')}")
                else:
                    print(f"  重新提交仍失败: {result.get('message')}")
            else:
                print("  重新登录失败")
        else:
            print(f"  提交结果: status={status}, {result.get('message')}")

        return result

    # ---------- QQ 邮箱监控 ----------

    def _imap_connect(self):
        """连接 QQ 邮箱 IMAP 并选中收件箱。"""
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(self.helper_email, self.imap_auth)
        mail.select("INBOX")
        return mail

    def check_mail(self, since_hours: int = 24) -> list:
        """
        检查 QQ 邮箱中来自 HNLAT 的邮件。

        通过 IMAP 搜索 FROM/ SUBJECT 关键词，
        返回邮件列表（含是否带 PDF 附件的信息）。
        """
        print(f"[邮箱] 检查最近 {since_hours} 小时的邮件...")
        results = []
        try:
            mail = self._imap_connect()
            since = (datetime.now() - timedelta(hours=since_hours)).strftime(
                "%d-%b-%Y"
            )

            queries = [
                f'(FROM "hnlat" SINCE {since})',
                f'(SUBJECT "paper" SINCE {since})',
            ]

            for q in queries:
                st, msgs = mail.search(None, q)
                if not msgs[0]:
                    continue
                for eid in reversed(msgs[0].split()):
                    eid_str = eid.decode()
                    if eid_str in [r["id"] for r in results]:
                        continue

                    _, raw = mail.fetch(eid, "(RFC822)")
                    msg = email_lib.message_from_bytes(raw[0][1])

                    # 解码邮件主题
                    subj = self._decode_header(msg.get("Subject", ""))

                    # 检查附件
                    has_pdf = False
                    attachments = []
                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            fn = self._decode_header(part.get_filename() or "")
                            if fn.lower().endswith(".pdf"):
                                has_pdf = True
                                attachments.append(fn)

                    results.append({
                        "id": eid_str,
                        "subject": subj,
                        "date": msg.get("Date", ""),
                        "has_pdf": has_pdf,
                        "attachments": attachments,
                    })

            mail.logout()
        except Exception as e:
            print(f"  邮箱错误: {e}")

        pdf_count = sum(1 for r in results if r["has_pdf"])
        print(f"  找到 {len(results)} 封邮件，其中 {pdf_count} 封含 PDF")
        return results

    def download_pdfs(self, since_hours: int = 72) -> list:
        """
        从 QQ 邮箱下载 HNLAT 发来的 PDF 附件。

        自动跳过已下载的文件（通过文件名判断）。
        PDF 保存到 config.json 中 download_dir 指定的目录。
        """
        print("[下载] 扫描邮箱中的 PDF 附件...")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []

        try:
            mail = self._imap_connect()
            since = (datetime.now() - timedelta(hours=since_hours)).strftime(
                "%d-%b-%Y"
            )

            queries = [
                f'(FROM "hnlat" SINCE {since})',
                f'(SUBJECT "paper" SINCE {since})',
            ]

            seen_fns = set()

            for q in queries:
                st, msgs = mail.search(None, q)
                if not msgs[0]:
                    continue
                for eid in msgs[0].split():
                    _, raw = mail.fetch(eid, "(RFC822)")
                    msg = email_lib.message_from_bytes(raw[0][1])

                    for part in msg.walk():
                        if part.get_content_disposition() != "attachment":
                            continue
                        fn = self._decode_header(part.get_filename() or "")
                        if not fn.lower().endswith(".pdf"):
                            continue
                        if fn in seen_fns:
                            continue
                        seen_fns.add(fn)

                        save_path = self.download_dir / fn
                        if save_path.exists():
                            print(f"  跳过 (已存在): {fn}")
                            continue

                        pdf_bytes = part.get_payload(decode=True)
                        save_path.write_bytes(pdf_bytes)
                        size_mb = len(pdf_bytes) / 1024 / 1024
                        print(f"  已保存: {fn} ({size_mb:.1f} MB)")
                        downloaded.append(str(save_path))

            mail.logout()
        except Exception as e:
            print(f"  下载错误: {e}")

        return downloaded

    # ---------- 辅助方法 ----------

    @staticmethod
    def _decode_header(raw_value: str) -> str:
        """解码邮件头（处理编码的主题/文件名）。"""
        if not raw_value:
            return ""
        decoded = email_lib.header.decode_header(raw_value)
        parts = []
        for fragment, charset in decoded:
            if isinstance(fragment, bytes):
                parts.append(fragment.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(fragment)
        return "".join(parts)


# ===================== 命令行入口 =====================

def main():
    config = load_config()
    bot = HNLATBot(config)

    parser = argparse.ArgumentParser(
        description="HNLAT 纬度文献互助平台 — 自动化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --doi 10.1038/s41586-024-08329-5     提交单篇 DOI
  %(prog)s --doi-list dois.txt                   批量提交 DOI 列表
  %(prog)s --title "paper name"                  按标题提交
  %(prog)s --monitor                             检查邮箱
  %(prog)s --download                            下载所有 PDF
  %(prog)s --doi 10.xxx --loop                   提交后持续监控
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doi", help="提交单个 DOI")
    group.add_argument("--doi-list", help="DOI 列表文件（每行一个）")
    group.add_argument("--title", help="按论文标题提交")
    group.add_argument("--monitor", action="store_true", help="检查邮箱")
    group.add_argument("--download", action="store_true", help="下载邮箱中的 PDF")
    parser.add_argument(
        "--loop", action="store_true",
        help="提交后持续监控邮箱，自动下载新 PDF",
    )
    parser.add_argument(
        "--loop-interval", type=int, default=0,
        help=f"监控间隔秒数 (默认使用 config 中的值)",
    )
    args = parser.parse_args()

    interval = args.loop_interval or bot.loop_interval

    # --- 仅邮箱操作（不需要登录）---

    if args.download:
        dl = bot.download_pdfs()
        print(f"\n完成，共下载 {len(dl)} 个 PDF 到 {bot.download_dir}")
        return

    if args.monitor:
        emails = bot.check_mail()
        for e in emails:
            tag = " [PDF]" if e["has_pdf"] else ""
            print(f"  {e['date']} | {e['subject']}{tag}")
        dl = bot.download_pdfs()
        print(f"\n新下载 {len(dl)} 个 PDF")
        return

    # --- 需要登录的操作 ---

    if not bot.login():
        print("登录失败，请检查 config.json 中的账号密码。")
        sys.exit(1)

    if args.doi:
        result = bot.submit(doi=args.doi)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.title:
        result = bot.submit(title=args.title)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.doi_list:
        fpath = Path(args.doi_list)
        if not fpath.exists():
            print(f"文件不存在: {fpath}")
            sys.exit(1)

        dois = [
            line.strip()
            for line in fpath.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        print(f"共 {len(dois)} 个 DOI，开始处理...\n")

        for i, doi in enumerate(dois, 1):
            print(f"\n{'=' * 50}")
            print(f"[{i}/{len(dois)}] {doi}")
            print(f"{'=' * 50}")
            bot.submit(doi=doi)
            time.sleep(2)

    # --- 提交后检查 & 可选持续监控 ---

    print("\n[后续] 检查邮箱中是否已有 PDF...")
    dl = bot.download_pdfs()
    print(f"本次新下载 {len(dl)} 个 PDF")

    if args.loop:
        print(f"\n[持续监控] 每 {interval} 秒检查一次，Ctrl+C 停止。")
        try:
            while True:
                dl = bot.download_pdfs()
                if dl:
                    now = datetime.now().strftime("%H:%M:%S")
                    print(f"[{now}] 新下载 {len(dl)} 个 PDF: {dl}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n已停止监控。")


if __name__ == "__main__":
    main()
