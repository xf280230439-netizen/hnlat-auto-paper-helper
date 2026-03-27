#!/usr/bin/env python3
"""
=============================================================
  HNLAT 纬度文献互助平台 — 自动化工具 v2.0
=============================================================

支持平台：
  1. paper.hnlat.com  — 文献互助（任意网络可用）
  2. spis.hnlat.com   — 机构全文数据库（需校园IP或机构认证）

功能：
  1. 自动登录（通过 SSO 单点登录，两平台共用账号）
  2. 通过 DOI 或论文标题提交文献求助 / 搜索全文
  3. 通过 IMAP 监控 QQ 邮箱，自动下载 PDF 附件
  4. 支持批量提交 + 持续监控
  5. 智能降级：spis 不可用时自动切换到 paper 互助

使用前：
  1. 复制 config.example.json 为 config.json
  2. 填入你的账号信息（详见 README.md）
  3. pip install requests

命令示例：
  # 使用默认平台（paper 互助）
  python hnlat_auto.py --doi 10.1038/s41586-024-08329-5
  python hnlat_auto.py --title "Some paper title"
  python hnlat_auto.py --doi-list dois.txt

  # 指定平台
  python hnlat_auto.py --doi 10.1038/... --site paper   # paper.hnlat.com 互助
  python hnlat_auto.py --doi 10.1038/... --site spis    # spis.hnlat.com 全文库
  python hnlat_auto.py --doi 10.1038/... --site auto    # 自动选择（spis优先，失败降级）

  # 邮箱操作
  python hnlat_auto.py --monitor
  python hnlat_auto.py --download
  python hnlat_auto.py --doi 10.xxx --loop
=============================================================
"""

import argparse
import email as email_lib
import hashlib
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
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ===================== 常量 =====================
SSO_BASE = "https://sso.hnlat.com"

# paper.hnlat.com 常量
PAPER_BASE = "https://paper.hnlat.com"
PAPER_SERVICE_URL = (
    "https://paper.hnlat.com/loginCenter"
    "?sourceurl=https%3A%2F%2Fpaper.hnlat.com%2F"
)

# spis.hnlat.com 常量
SPIS_BASE = "https://spis.hnlat.com"
SPIS_SERVICE_URL = "http://spis.hnlat.com"   # SSO 回调使用 http
SPIS_API_BASE = "https://spis.hnlat.com/api"

# QQ 邮箱
IMAP_SERVER = "imap.qq.com"
IMAP_PORT = 993

SITE_PAPER = "paper"
SITE_SPIS  = "spis"
SITE_AUTO  = "auto"


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

    required = ["hnlat_username", "hnlat_password", "qq_email", "qq_imap_auth"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        print(f"config.json 中以下字段为空，请填写: {', '.join(missing)}")
        sys.exit(1)

    return config


def _make_session() -> requests.Session:
    """创建标准 HTTP session。"""
    s = requests.Session()
    s.verify = False
    s.trust_env = False
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/132.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    })
    return s


# ===================== SSO 登录工具函数 =====================

def sso_login(session: requests.Session, username: str, password: str,
              service_url: str, site_label: str = "") -> bool:
    """
    通用 SSO 登录：适用于 paper 和 spis 两个站点。
    返回 True 表示登录成功。
    """
    label = f"[{site_label}] " if site_label else ""
    print(f"{label}[登录] 正在通过 SSO 登录...")

    # Step 1: 建立 SSO 会话
    r = session.get(
        f"{SSO_BASE}/login",
        params={"service": service_url},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  无法访问 SSO 登录页 (HTTP {r.status_code})")
        return False

    # Step 2: 提交账号密码
    r = session.post(
        f"{SSO_BASE}/login/username",
        data={
            "un": username,
            "pw": password,
            "service": service_url,
            "loginType": "1",
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": SSO_BASE,
            "Referer": (
                f"{SSO_BASE}/login?service="
                + urllib.parse.quote(service_url, safe="")
            ),
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )

    try:
        data = r.json()
    except Exception:
        print(f"  SSO 响应解析失败: {r.text[:200]}")
        return False

    if data.get("status") != 1:
        print(f"  登录失败: {data.get('message', '未知错误')}")
        return False

    print(f"  SSO 认证成功")

    # Step 3: 跟随 SSO 回调链接（建立目标站点会话）
    location = data.get("body", {}).get("location", "")
    if location:
        session.get(location, timeout=30, allow_redirects=True)
    else:
        # 直接访问 service URL 触发 ticket 校验
        session.get(service_url, timeout=30, allow_redirects=True)

    return True


# ===================== paper.hnlat.com 客户端 =====================

class PaperBot:
    """paper.hnlat.com 文献互助自动化客户端。"""

    def __init__(self, config: dict):
        self.username = config["hnlat_username"]
        self.password = config["hnlat_password"]
        self.helper_email = config["qq_email"]
        self.imap_auth = config["qq_imap_auth"]
        self.download_dir = Path(config.get("download_dir", "./downloads"))
        self.loop_interval = config.get("loop_interval_seconds", 300)

        self.session = _make_session()
        self.logged_in = False

    def login(self) -> bool:
        ok = sso_login(
            self.session, self.username, self.password,
            PAPER_SERVICE_URL, site_label="paper"
        )
        if not ok:
            return False

        # 验证会话
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
        print(f"  [paper] 登录成功！今日已用 {body.get('todayTotal')} 次，"
              f"剩余 {body.get('todayRestTotal')} 次")
        self.logged_in = True
        return True

    def lookup_doi(self, doi: str) -> dict:
        print(f"[paper] [查询] DOI: {doi}")
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

    def submit(self, doi: str = "", title: str = "", doi_data: dict = None) -> dict:
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
        print(f"[paper] [提交] {label}")

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
            print(f"  [paper] 提交成功！记录编号 #{result.get('body')}")
        elif status in (2008, 1001206):
            print(f"  [paper] 该文献已在处理队列中 (status={status})")
        elif status == 10086:
            print("  [paper] 登录态过期，正在重新登录...")
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
                    print(f"  [paper] 重新提交成功！记录 #{result.get('body')}")
                else:
                    print(f"  [paper] 重新提交仍失败: {result.get('message')}")
            else:
                print("  [paper] 重新登录失败")
        else:
            print(f"  [paper] 提交结果: status={status}, {result.get('message')}")

        return result

    # ---------- QQ 邮箱监控 ----------

    def _imap_connect(self):
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(self.helper_email, self.imap_auth)
        mail.select("INBOX")
        return mail

    def check_mail(self, since_hours: int = 24) -> list:
        print(f"[邮箱] 检查最近 {since_hours} 小时的邮件...")
        results = []
        try:
            mail = self._imap_connect()
            since = (datetime.now() - timedelta(hours=since_hours)).strftime("%d-%b-%Y")
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
                    subj = self._decode_header(msg.get("Subject", ""))
                    has_pdf = False
                    attachments = []
                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            fn = self._decode_header(part.get_filename() or "")
                            if fn.lower().endswith(".pdf"):
                                has_pdf = True
                                attachments.append(fn)
                    results.append({
                        "id": eid_str, "subject": subj,
                        "date": msg.get("Date", ""),
                        "has_pdf": has_pdf, "attachments": attachments,
                    })
            mail.logout()
        except Exception as e:
            print(f"  邮箱错误: {e}")
        pdf_count = sum(1 for r in results if r["has_pdf"])
        print(f"  找到 {len(results)} 封邮件，其中 {pdf_count} 封含 PDF")
        return results

    def download_pdfs(self, since_hours: int = 72) -> list:
        """
        扫描 QQ 邮箱，下载所有 PDF 附件。

        改进：
        - 下载成功后将该封邮件标记为「已读」
        - 通过 MD5 检测本地重复文件（文件名不同但内容相同也会跳过）
        - 打印下载汇总（新增 / 跳过已读 / 跳过重复 / 失败）
        """
        print("[下载] 扫描邮箱中的 PDF 附件...")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # 构建本地 MD5 集合，用于内容去重
        local_md5s: set[str] = set()
        for p in self.download_dir.rglob("*.pdf"):
            try:
                local_md5s.add(hashlib.md5(p.read_bytes()).hexdigest())
            except Exception:
                pass

        downloaded: list[str] = []
        skipped_exists = 0
        skipped_dup    = 0
        failed         = 0

        try:
            mail = self._imap_connect()
            since = (datetime.now() - timedelta(hours=since_hours)).strftime("%d-%b-%Y")
            queries = [
                f'(FROM "hnlat" SINCE {since})',
                f'(SUBJECT "paper" SINCE {since})',
            ]
            seen_email_ids: set[str] = set()   # 防止同一封邮件被两条 query 重复处理

            for q in queries:
                st, msgs = mail.search(None, q)
                if not msgs[0]:
                    continue

                for eid in msgs[0].split():
                    eid_str = eid.decode()
                    if eid_str in seen_email_ids:
                        continue
                    seen_email_ids.add(eid_str)

                    _, raw = mail.fetch(eid, "(RFC822)")
                    msg = email_lib.message_from_bytes(raw[0][1])

                    email_has_new_pdf = False   # 本封邮件是否有新 PDF 被成功保存

                    for part in msg.walk():
                        if part.get_content_disposition() != "attachment":
                            continue
                        fn = self._decode_header(part.get_filename() or "")
                        if not fn.lower().endswith(".pdf"):
                            continue

                        pdf_bytes = part.get_payload(decode=True)
                        if not pdf_bytes:
                            continue

                        # 内容 MD5 去重（优先于文件名判断）
                        md5 = hashlib.md5(pdf_bytes).hexdigest()
                        if md5 in local_md5s:
                            print(f"  跳过 (内容重复): {fn}")
                            skipped_dup += 1
                            continue

                        # 文件名去重（同名文件直接跳过）
                        save_path = self.download_dir / fn
                        if save_path.exists():
                            print(f"  跳过 (已存在): {fn}")
                            skipped_exists += 1
                            continue

                        # 保存文件
                        save_path.write_bytes(pdf_bytes)
                        local_md5s.add(md5)   # 加入缓存避免同次运行内重复
                        size_mb = len(pdf_bytes) / 1024 / 1024
                        print(f"  已保存: {fn} ({size_mb:.1f} MB)")
                        downloaded.append(str(save_path))
                        email_has_new_pdf = True

                    # 只要本封邮件有 PDF 成功下载，就标为已读
                    if email_has_new_pdf:
                        try:
                            mail.store(eid, "+FLAGS", "\\Seen")
                        except Exception as e:
                            print(f"  [警告] 标记已读失败: {e}")

            mail.logout()

        except Exception as e:
            print(f"  下载错误: {e}")
            failed += 1

        # 汇总输出
        print(f"\n[下载完成] 新增 {len(downloaded)} 个 | "
              f"跳过已存在 {skipped_exists} 个 | "
              f"跳过内容重复 {skipped_dup} 个"
              + (f" | 错误 {failed} 次" if failed else ""))

        # 重复文件检测（本次新下载内部互查，理论上不应发生，做保险提示）
        if len(downloaded) > 1:
            new_md5s: dict[str, str] = {}
            for fp in downloaded:
                try:
                    m = hashlib.md5(Path(fp).read_bytes()).hexdigest()
                    if m in new_md5s:
                        print(f"  [注意] 重复内容: {Path(fp).name} == {Path(new_md5s[m]).name}")
                    else:
                        new_md5s[m] = fp
                except Exception:
                    pass

        return downloaded

    @staticmethod
    def _decode_header(raw_value: str) -> str:
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


# ===================== spis.hnlat.com 客户端 =====================

class SpisBot:
    """
    spis.hnlat.com 机构全文数据库客户端。

    注意：
      - 全文直接下载需要校园网 IP 或机构认证（resourceConfig status=1）
      - 非校园网时 status=10011，仍可提交文献投递请求（走 spis 渠道互助）
      - 账号密码与 paper.hnlat.com 相同（同一套 HNLAT SSO）
    """

    def __init__(self, config: dict):
        self.username = config["hnlat_username"]
        self.password = config["hnlat_password"]
        self.helper_email = config["qq_email"]
        self.download_dir = Path(config.get("download_dir", "./downloads"))

        # spis 可以有独立账号（可选）
        self.spis_username = config.get("spis_username") or config["hnlat_username"]
        self.spis_password = config.get("spis_password") or config["hnlat_password"]

        self.session = _make_session()
        self.session.headers.update({
            "Referer": SPIS_BASE + "/",
            "Origin": SPIS_BASE,
        })
        self.logged_in = False
        self.campus_ip = False   # 是否在校园网

    def login(self) -> bool:
        ok = sso_login(
            self.session, self.spis_username, self.spis_password,
            SPIS_SERVICE_URL, site_label="spis"
        )
        if not ok:
            return False

        # 访问首页完成 cookie 建立
        self.session.get(SPIS_BASE + "/", timeout=30, allow_redirects=True)

        # 检查权限级别
        try:
            r = self.session.get(f"{SPIS_API_BASE}/page/resourceConfig", timeout=15)
            rc = r.json()
            rc_status = rc.get("status")
            if rc_status == 1:
                self.campus_ip = True
                print(f"  [spis] 登录成功！检测到校园网 IP，可直接下载全文")
            elif rc_status == 10011:
                self.campus_ip = False
                print(f"  [spis] 登录成功（非校园网 IP），将通过互助渠道提交")
            else:
                print(f"  [spis] 登录成功，权限状态: {rc_status}")
        except Exception as e:
            print(f"  [spis] 权限检查异常（跳过）: {e}")

        # 验证用户信息
        try:
            r2 = self.session.get(f"{SPIS_API_BASE}/data/info", timeout=15)
            info = r2.json()
            if info.get("status") == 1:
                user = info.get("body", {}).get("user", {})
                print(f"  [spis] 用户: {user.get('nickname', '')} "
                      f"({user.get('orgName', '')})")
                self.logged_in = True
                return True
        except Exception:
            pass

        self.logged_in = True
        return True

    def search_article(self, doi: str = "", title: str = "") -> dict | None:
        """
        在 spis 数据库中搜索文章。
        目前 spis 的搜索 API 需要特定参数格式，使用 /article/list/facet/data/spis 端点。
        返回文章信息 dict 或 None。
        """
        print(f"[spis] [搜索] " + (f"DOI: {doi}" if doi else f"标题: {title[:50]}"))

        # 尝试通过 DOI 直接构造文章 href
        if doi:
            doc_href = f"https://doi.org/{doi}"
        else:
            doc_href = ""

        # spis 的全文检索走前端路由，后端 /article/search/data 需要特定格式
        # 目前已知可用的搜索接口：获取站内推荐文章列表
        # 对于 DOI/标题搜索，构造投递 payload 直接提交
        return {
            "docTitle": title or f"Article DOI: {doi}",
            "docHref": doc_href,
            "doi": doi,
        }

    def request_delivery(self, doi: str = "", title: str = "",
                         doc_href: str = "") -> dict:
        """
        通过 spis 渠道提交文献投递请求。
        对应 /api/delivery/request/data 接口。

        注意：
        - 需要有效的文章 docHref（文章页面 URL）
        - helpChannel 自动设为 2（spis 渠道）
        - 返回投递结果，status=1 为成功
        """
        if not doc_href and doi:
            doc_href = f"https://doi.org/{doi}"

        payload = {
            "docTitle": title or (f"DOI: {doi}" if doi else ""),
            "docHref": doc_href,
            "openUri": doc_href,
            "helperEmail": self.helper_email,
            "doi": doi,
            "helpChannel": 2,
            "docType": 1,
            "anonymous": False,
            "remark": "",
            "pagesNumber": "",
        }

        label = doi or (title[:50] + "..." if len(title) > 50 else title)
        print(f"[spis] [投递] {label}")

        try:
            r = self.session.post(
                f"{SPIS_API_BASE}/delivery/request/data",
                params={
                    "referer": urllib.parse.quote(
                        "https://spis.hnlat.com/action/doSearch", safe=""
                    ),
                    "pageObj": "",
                    "deliveryCode": "",
                },
                json=payload,
                headers={
                    "Content-Type": "application/json;charset=UTF-8",
                    "Referer": f"{SPIS_BASE}/action/doSearch",
                },
                timeout=30,
            )
            result = r.json()
            status = result.get("status")

            if status == 1:
                print(f"  [spis] 投递成功！记录 #{result.get('body')}")
            elif status == 10086:
                print("  [spis] 登录态过期，重新登录...")
                if self.login():
                    return self.request_delivery(doi=doi, title=title, doc_href=doc_href)
            else:
                msg = result.get("message", "")
                body_status = (result.get("body") or {}).get("status", "") if isinstance(result.get("body"), dict) else ""
                print(f"  [spis] 投递结果: status={status} {body_status}, {msg}")

            return result
        except Exception as e:
            print(f"  [spis] 投递异常: {e}")
            return {"status": -1, "message": str(e)}

    def get_my_deliveries(self, page: int = 1, size: int = 10) -> list:
        """获取我的 spis 投递记录（含下载链接）。"""
        try:
            r = self.session.get(
                f"{SPIS_API_BASE}/delivery/user/data",
                params={"pageNum": page, "pageSize": size},
                timeout=15,
            )
            data = r.json()
            if data.get("status") == 1:
                datas = data.get("body", {}).get("datas", [])
                print(f"[spis] 共 {len(datas)} 条投递记录")
                for d in datas:
                    status_map = {9: "已完成", 0: "待处理", 1: "处理中", 2: "已取消"}
                    s = status_map.get(d.get("status"), str(d.get("status")))
                    dl_url = d.get("downloadUrl", "")
                    print(f"  #{d['id']} [{s}] {d.get('docTitle', '')[:50]}")
                    if dl_url:
                        print(f"    下载链接: {dl_url}")
                return datas
            else:
                print(f"[spis] 获取投递记录失败: {data.get('message')}")
                return []
        except Exception as e:
            print(f"[spis] 获取投递记录异常: {e}")
            return []

    def download_from_url(self, url: str, filename: str) -> str | None:
        """从指定 URL 下载文件（用于下载 spis 已完成的投递）。"""
        self.download_dir.mkdir(parents=True, exist_ok=True)
        save_path = self.download_dir / filename

        if save_path.exists():
            print(f"  跳过 (已存在): {filename}")
            return str(save_path)

        try:
            r = self.session.get(url, timeout=60, stream=True)
            if r.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                size_mb = save_path.stat().st_size / 1024 / 1024
                print(f"  已保存: {filename} ({size_mb:.1f} MB)")
                return str(save_path)
            else:
                print(f"  下载失败: HTTP {r.status_code}")
                return None
        except Exception as e:
            print(f"  下载异常: {e}")
            return None


# ===================== 统一入口函数 =====================

def submit_paper(config: dict, doi: str = "", title: str = "",
                 site: str = SITE_AUTO) -> dict:
    """
    统一的文献提交入口，支持三种站点选择：
      - paper: 直接用 paper.hnlat.com 互助
      - spis:  直接用 spis.hnlat.com 投递
      - auto:  先尝试 spis，失败后降级到 paper
    """
    if site == SITE_PAPER:
        return _submit_via_paper(config, doi=doi, title=title)

    elif site == SITE_SPIS:
        return _submit_via_spis(config, doi=doi, title=title)

    elif site == SITE_AUTO:
        print("[auto] 尝试 spis.hnlat.com 投递...")
        result = _submit_via_spis(config, doi=doi, title=title)
        spis_ok = result.get("status") == 1
        if spis_ok:
            return result
        else:
            print("[auto] spis 投递失败，降级到 paper.hnlat.com 互助...")
            return _submit_via_paper(config, doi=doi, title=title)

    else:
        print(f"未知站点: {site}，使用默认 paper 站")
        return _submit_via_paper(config, doi=doi, title=title)


def _submit_via_paper(config: dict, doi: str = "", title: str = "") -> dict:
    bot = PaperBot(config)
    if not bot.login():
        print("[paper] 登录失败，请检查账号密码")
        return {"status": -1, "message": "登录失败"}
    return bot.submit(doi=doi, title=title)


def _submit_via_spis(config: dict, doi: str = "", title: str = "") -> dict:
    bot = SpisBot(config)
    if not bot.login():
        print("[spis] 登录失败，请检查账号密码")
        return {"status": -1, "message": "登录失败"}

    doc_href = f"https://doi.org/{doi}" if doi else ""
    return bot.request_delivery(doi=doi, title=title, doc_href=doc_href)


# ===================== 命令行入口 =====================

def main():
    config = load_config()

    parser = argparse.ArgumentParser(
        description="HNLAT 纬度文献互助平台 — 自动化工具 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
站点说明:
  paper  paper.hnlat.com 互助（任意网络可用，PDF 发到 QQ 邮箱）
  spis   spis.hnlat.com 机构全文库（需校园网可直接下载，非校园网走互助渠道）
  auto   自动选择（spis 优先，失败后降级到 paper）[默认]

示例:
  %(prog)s --doi 10.1038/s41586-024-08329-5              提交单篇 DOI（auto 模式）
  %(prog)s --doi 10.1038/... --site paper                指定 paper 互助
  %(prog)s --doi 10.1038/... --site spis                 指定 spis 投递
  %(prog)s --doi-list dois.txt --site auto               批量提交（auto 模式）
  %(prog)s --title "paper name"                          按标题提交
  %(prog)s --monitor                                     检查 QQ 邮箱
  %(prog)s --download                                    下载所有 PDF（QQ 邮箱）
  %(prog)s --spis-deliveries                             查看 spis 投递记录
  %(prog)s --doi 10.xxx --loop                           提交后持续监控邮箱
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doi", help="提交单个 DOI")
    group.add_argument("--doi-list", help="DOI 列表文件（每行一个）")
    group.add_argument("--title", help="按论文标题提交")
    group.add_argument("--monitor", action="store_true", help="检查 QQ 邮箱")
    group.add_argument("--download", action="store_true", help="下载 QQ 邮箱中的 PDF")
    group.add_argument("--spis-deliveries", action="store_true", help="查看 spis 投递记录（含下载链接）")

    parser.add_argument(
        "--site", choices=[SITE_PAPER, SITE_SPIS, SITE_AUTO],
        default=SITE_AUTO,
        help=f"提交站点: paper/spis/auto（默认: {SITE_AUTO}）",
    )
    parser.add_argument(
        "--loop", action="store_true",
        help="提交后持续监控 QQ 邮箱，自动下载新 PDF",
    )
    parser.add_argument(
        "--loop-interval", type=int, default=0,
        help="监控间隔秒数（默认使用 config 中的值）",
    )

    args = parser.parse_args()

    # --- 仅邮箱操作（不需要登录 paper/spis）---

    if args.download:
        bot = PaperBot(config)
        dl = bot.download_pdfs()
        print(f"保存目录: {bot.download_dir.resolve()}")
        return

    if args.monitor:
        bot = PaperBot(config)
        emails = bot.check_mail()
        for e in emails:
            tag = " [PDF]" if e["has_pdf"] else ""
            print(f"  {e['date']} | {e['subject']}{tag}")
        dl = bot.download_pdfs()
        print(f"\n新下载 {len(dl)} 个 PDF")
        return

    # --- spis 投递记录查看 ---

    if args.spis_deliveries:
        bot = SpisBot(config)
        if not bot.login():
            print("[spis] 登录失败")
            sys.exit(1)
        bot.get_my_deliveries(size=20)
        return

    # --- 文献提交 ---

    interval = args.loop_interval or config.get("loop_interval_seconds", 300)

    print(f"\n[站点] 使用 {args.site.upper()} 模式")
    print("=" * 55)

    if args.doi:
        result = submit_paper(config, doi=args.doi, site=args.site)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.title:
        result = submit_paper(config, title=args.title, site=args.site)
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
            submit_paper(config, doi=doi, site=args.site)
            time.sleep(2)

    # --- 提交后检查 QQ 邮箱（仅 paper 模式和 auto 降级到 paper 时有意义）---

    if args.site in (SITE_PAPER, SITE_AUTO):
        print("\n[后续] 检查 QQ 邮箱中是否已有 PDF...")
        mail_bot = PaperBot(config)
        dl = mail_bot.download_pdfs()
        print(f"本次新下载 {len(dl)} 个 PDF")

    if args.loop:
        print(f"\n[持续监控] 每 {interval} 秒检查一次 QQ 邮箱，Ctrl+C 停止。")
        mail_bot = PaperBot(config)
        try:
            while True:
                dl = mail_bot.download_pdfs()
                if dl:
                    now = datetime.now().strftime("%H:%M:%S")
                    print(f"[{now}] 新下载 {len(dl)} 个 PDF: {dl}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n已停止监控。")


if __name__ == "__main__":
    main()
