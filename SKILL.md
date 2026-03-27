---
name: hnlat-auto-paper-helper
description: Automatically submit papers to paper.hnlat.com or spis.hnlat.com by DOI/title, monitor QQ mailbox for PDF attachments, and download papers. Supports dual-platform selection (paper互助 / spis机构全文库) with auto-fallback. Use this skill when users need to submit academic papers, track download status, or batch process literature from HNLAT platform.
allowed-tools: 
disable: false
---

# HNLAT 自动文献助手 v2.1

脚本目录：`C:\Users\xf280\.workbuddy\skills\hnlat-auto-paper-helper\scripts\`  
配置文件：`scripts\config.json`（账号：280230439，QQ邮箱：2794204788@qq.com）

---

## 平台说明

| 平台 | 用途 | 网络要求 |
|------|------|---------|
| paper.hnlat.com | 文献互助，PDF 发到 QQ 邮箱 | 任意网络 |
| spis.hnlat.com | 机构全文库，可直接下载 | 校园网（非校园网自动转互助） |

默认使用 `auto` 模式：优先 spis，失败自动降级 paper。

---

## 常用命令速查

### 提交文献

```bash
# 单篇（auto 模式）
python hnlat_auto.py --doi 10.1038/s41586-024-08329-5
python hnlat_auto.py --title "paper title here"

# 指定平台
python hnlat_auto.py --doi 10.xxx --site paper
python hnlat_auto.py --doi 10.xxx --site spis

# 批量（每行一个 DOI）
python hnlat_auto.py --doi-list dois.txt
```

### 下载 PDF（QQ 邮箱）

```bash
# 扫描邮箱并下载所有新 PDF（下载成功的邮件自动标已读，MD5 去重）
python hnlat_auto.py --download

# 检查邮件状态（不下载）
python hnlat_auto.py --monitor

# 提交后持续监控邮箱（每 5 分钟检查一次）
python hnlat_auto.py --doi 10.xxx --loop
```

### spis 投递记录

```bash
# 查看投递历史及下载链接（status=9 为已完成）
python hnlat_auto.py --spis-deliveries
```

### 公众号文章解析

```bash
# 解析文章，自动 OCR 图片中的标题/DOI
python wechat_parser.py "https://mp.weixin.qq.com/s/xxxxx"

# 解析并直接提交到 HNLAT
python wechat_parser.py "https://mp.weixin.qq.com/s/xxxxx" --submit

# 跳过 OCR（更快）
python wechat_parser.py "URL" --no-ocr
```

---

## 完整工作流程

**标准流程（单篇）：**
1. `python hnlat_auto.py --doi 10.xxx` — 提交
2. 等待邮件（通常 5–30 分钟）
3. `python hnlat_auto.py --download` — 下载 PDF，已处理邮件自动标已读

**公众号文章批量下载流程：**
1. `python wechat_parser.py "URL" --submit` — 解析文章并提交所有文献
2. 等待邮件
3. `python hnlat_auto.py --download` — 批量下载

**spis 直接下载流程（校园网）：**
1. `python hnlat_auto.py --doi 10.xxx --site spis`
2. `python hnlat_auto.py --spis-deliveries` — 查看 downloadUrl
3. 直接访问 downloadUrl 下载

---

## 下载机制说明

`--download` 命令的去重逻辑（按优先级）：
1. **MD5 内容去重**：计算 PDF 字节 MD5，与本地所有 PDF 比对，相同内容无论文件名如何都跳过
2. **文件名去重**：同名文件直接跳过
3. **已读标记**：有 PDF 成功下载的邮件自动标记为「已读」（IMAP `\Seen`）
4. 运行结束打印汇总：`新增 X | 跳过已存在 X | 跳过内容重复 X`

---

## OCR 引擎（wechat_parser）

按优先级自动选择，安装其一即可：

```bash
pip install easyocr              # 推荐：中英文，安装简单
pip install paddleocr paddlepaddle  # 高精度备选
```

未安装时跳过 OCR，不影响文字提取。OCR 来源的结果标注 `[图片OCR]`。

---

## 关键技术参数

- SSO: `https://sso.hnlat.com`（paper/spis 共用）
- spis SSO service URL 用 `http://`（非 https）
- spis API: `https://spis.hnlat.com/api`
- `helpChannel=5` → paper 渠道；`helpChannel=2` → spis 渠道
- spis `status=10011` = 非校园网 IP（正常，转互助渠道）
- IMAP: `imap.qq.com:993`（SSL）

---

## 脚本目录

| 文件 | 用途 |
|------|------|
| `hnlat_auto.py` | 核心脚本（提交、下载、监控） |
| `wechat_parser.py` | 公众号文章解析 + 图片 OCR |
| `api_server.py` | Flask HTTP API 服务 |
| `telegram_bot.py` | Telegram Bot 远程控制 |
| `auto_download_flow.py` | 全流程自动下载 |
| `monitor_loop.py` | 独立持续监控 |
| `reorganize_all.py` | PDF 按主题自动分类 |
| `extract_abstracts.py` | PDF 摘要提取 |
| `download_v3.py` | Playwright 浏览器下载（处理 JS 页面） |
| `config.json` | 账号配置（不上传 git） |
| `config.example.json` | 配置模板 |
