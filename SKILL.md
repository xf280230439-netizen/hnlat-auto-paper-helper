# HNLAT 自动文献下载器 Skill

## 描述

自动化从 [paper.hnlat.com](https://paper.hnlat.com) 下载学术文献的工具。支持通过 DOI、论文标题、微信公众号文章自动提交文献求助，自动监控邮箱获取下载链接，并通过 Playwright 浏览器自动化完成 PDF 下载。

**关键词**: 文献下载, 论文下载, HNLAT, 学术资源, 自动化, DOI, 公众号解析, Playwright

## 功能特性

- 🔐 自动登录 paper.hnlat.com（SSO 统一认证）
- 📝 通过 DOI 或论文标题提交文献求助
- 📧 自动监控 QQ 邮箱获取下载链接
- 🌐 **Playwright 浏览器自动化下载**（解决 JavaScript 渲染页面）
- 📂 **自动分类整理文献**（按主题/关键词）
- 🔗 从微信公众号文章自动解析 DOI/标题
- 🌐 Web API 服务支持
- 🤖 Telegram Bot 集成

## 使用场景

- 下载学术论文或文献
- 通过 DOI 查找论文
- 从公众号文章中提取论文信息并下载
- 批量下载多篇论文并自动分类

## 快速开始

### 1. 安装依赖

```bash
pip install requests flask playwright PyMuPDF
playwright install chromium
```

### 2. 配置账号

编辑 `config.json`：

```json
{
  "hnlat_username": "你的HNLAT账号",
  "hnlat_password": "你的HNLAT密码",
  "qq_email": "你的QQ邮箱",
  "qq_imap_auth": "QQ邮箱授权码（16位）",
  "download_dir": "./downloads",
  "loop_interval_seconds": 300
}
```

### 3. 基本用法

#### 提交文献下载

```bash
# 通过 DOI
python hnlat_auto.py --doi 10.1038/s41586-024-08329-5

# 通过标题
python hnlat_auto.py --title "Deep learning for image recognition"

# 持续监控模式
python hnlat_auto.py --doi 10.xxx --loop
```

#### 解析公众号文章

```bash
python wechat_parser.py "https://mp.weixin.qq.com/s/xxxxx"
```

#### 检查邮箱并下载

```bash
python hnlat_auto.py --monitor
```

### 4. API 服务

```bash
python api_server.py
```

API 端点：
- `POST /submit` - 提交 DOI/标题
- `POST /parse_wechat` - 解析公众号文章
- `GET /check_mail` - 检查邮箱状态
- `GET /download` - 下载 PDF

## 核心流程

### 完整下载流程

```
1. 用户提交 DOI/标题/公众号链接
       ↓
2. hnlat_auto.py 登录 HNLAT 平台提交求助
       ↓
3. 平台处理（社区互助，几分钟到几小时）
       ↓
4. PDF 下载链接发送到 QQ 邮箱
       ↓
5. check_and_download.py 监控邮箱提取下载链接
       ↓
6. download_v3.py 使用 Playwright 打开链接并下载 PDF
       ↓
7. reorganize_all.py 自动分类整理文献
```

### 文件说明

| 文件 | 功能 |
|------|------|
| `hnlat_auto.py` | 核心脚本：登录、提交、监控邮箱 |
| `api_server.py` | Web API 服务 |
| `wechat_parser.py` | 公众号文章解析器 |
| `telegram_bot.py` | Telegram 机器人 |
| `check_and_download.py` | 检查邮箱并提取新下载链接 |
| `download_v3.py` | Playwright 浏览器自动化下载 |
| `reorganize_all.py` | 文献自动分类整理 |
| `extract_abstracts.py` | 提取 PDF 摘要（辅助分类） |

## 文献分类规则

默认分类主题：

1. **肠道菌群与代谢** - 短链脂肪酸、微生物代谢
2. **肠-肝轴与肠道干细胞** - 肠道器官轴
3. **肠-皮轴与皮肤健康** - 肠-皮双向通信
4. **衰老与抗衰老机制** - 热量限制、衰老研究
5. **肿瘤免疫** - 癌症免疫学
6. **微生物群落生态** - 微生物群落结构
7. **人工智能与微生物组** - ML 应用
8. **大型队列与精准医学** - 队列研究
9. **G蛋白偶联受体** - GPCR 研究

可在 `reorganize_all.py` 中自定义分类规则。

## 依赖

- Python 3.8+
- requests >= 2.28.0
- flask >= 2.0.0
- playwright >= 1.40.0
- PyMuPDF >= 1.23.0

## 部署

### 本地部署

```bash
cd hnlat-auto-paper-helper
pip install -r requirements.txt
playwright install chromium
cp config.example.json config.json
# 编辑 config.json
python api_server.py
```

### Docker 部署

```bash
docker build -t hnlat-downloader .
docker run -d -p 5000:5000 \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/downloads:/app/downloads \
  hnlat-downloader
```

## 安全提示

1. **不要提交 config.json**
2. **使用 QQ 邮箱授权码**（不是登录密码）
3. **定期更换密码**

## 更新日志

### 2026-03-26

**新增功能：**
- ✨ Playwright 浏览器自动化下载（解决 JS 渲染页面问题）
- ✨ 文献自动分类整理功能
- ✨ PDF 摘要提取辅助分类
- ✨ 邮箱下载链接提取脚本

**优化改进：**
- 🔧 修复邮箱附件检测（PDF 在邮件正文中而非附件）
- 🔧 Windows UTF-8 编码兼容
- 🔧 下载去重和文件名规范化

---

**部署位置**: `E:\qclaw\resources\openclaw\config\skills\hnlat-auto-paper-helper`

**最后更新**: 2026-03-27
