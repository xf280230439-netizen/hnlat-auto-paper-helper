# HNLAT 自动文献下载器

一个自动化工具，用于从 [paper.hnlat.com](https://paper.hnlat.com)（或通过 [spis.hnlat.com](https://spis.hnlat.com) SSO 登录）下载学术文献。

## 功能特性

- 自动登录 paper.hnlat.com（支持通过 spis.hnlat.com SSO 认证）
- 通过 DOI 或论文标题提交文献求助
- 自动监控 QQ 邮箱，下载 PDF 附件
- 支持批量提交和持续监控模式
- 支持从微信公众号文章自动解析 DOI/标题

## 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 配置账号

复制配置文件模板并填写你的信息：

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
  "hnlat_username": "你的HNLAT账号",
  "hnlat_password": "你的HNLAT密码",
  "qq_email": "你的QQ邮箱@qq.com",
  "qq_imap_auth": "QQ邮箱授权码",
  "download_dir": "./downloads",
  "loop_interval_seconds": 300
}
```

**获取QQ邮箱授权码**：
1. 登录 QQ 邮箱网页版
2. 设置 → 账户 → 开启 IMAP/SMTP 服务
3. 生成 16 位授权码（不是登录密码）

### 3. 使用方法

#### 提交单篇文献（通过 DOI）

```bash
python hnlat_auto.py --doi 10.1038/s41586-024-08329-5
```

#### 提交单篇文献（通过标题）

```bash
python hnlat_auto.py --title "Deep learning for image recognition"
```

#### 批量提交 DOI

创建一个文本文件 `dois.txt`，每行一个 DOI：

```
10.1038/s41586-024-08329-5
10.1126/science.adk9090
10.1016/j.cell.2024.01.001
```

然后运行：

```bash
python hnlat_auto.py --doi-list dois.txt
```

#### 检查邮箱状态

```bash
python hnlat_auto.py --monitor
```

#### 下载所有 PDF

```bash
python hnlat_auto.py --download
```

#### 提交后持续监控

```bash
python hnlat_auto.py --doi 10.xxx --loop
```

#### 从公众号文章自动提取并下载

```bash
python wechat_parser.py "https://mp.weixin.qq.com/s/xxxxx"
```

## 项目结构

```
.
├── hnlat_auto.py           # 核心自动化脚本
├── wechat_parser.py        # 公众号文章解析器
├── config.example.json     # 配置模板
├── config.json             # 你的配置（不提交到Git）
├── requirements.txt        # Python依赖
├── .gitignore             # Git忽略文件
├── downloads/             # 下载的PDF保存目录
└── README.md              # 本文件
```

## API 服务（可选）

启动 Web API 服务，通过 HTTP 请求提交文献：

```bash
python api_server.py
```

然后可以通过 HTTP 请求使用：

```bash
# 提交 DOI
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"doi": "10.1038/s41586-024-08329-5"}'

# 提交标题
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"title": "Deep learning for image recognition"}'

# 解析公众号文章
curl -X POST http://localhost:5000/parse_wechat \
  -H "Content-Type: application/json" \
  -d '{"url": "https://mp.weixin.qq.com/s/xxxxx"}'

# 检查邮箱
curl http://localhost:5000/check_mail

# 下载 PDF
curl http://localhost:5000/download
```

## 部署到服务器

### 使用 Docker

```bash
# 构建镜像
docker build -t hnlat-downloader .

# 运行容器
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/downloads:/app/downloads \
  --name hnlat \
  hnlat-downloader
```

### 使用 systemd（Linux）

```bash
# 复制服务文件
sudo cp hnlat.service /etc/systemd/system/

# 启用并启动服务
sudo systemctl enable hnlat
sudo systemctl start hnlat
```

## 与手机互动的方式

### 方案 1：Telegram Bot

部署后可以通过 Telegram 机器人远程控制：

1. 创建 Telegram Bot（通过 @BotFather）
2. 设置 `TELEGRAM_BOT_TOKEN` 环境变量
3. 运行 `python telegram_bot.py`

### 方案 2：微信企业号/公众号

通过企业微信或公众号的 webhook 接收消息并处理。

### 方案 3：邮件触发

发送邮件到指定地址，自动解析并下载文献。

## 注意事项

1. **账号安全**：`config.json` 包含敏感信息，已添加到 `.gitignore`，请勿提交到 Git
2. **下载频率**：避免过于频繁的请求，建议间隔 2-5 秒
3. **邮箱监控**：持续监控模式会每 5 分钟检查一次邮箱
4. **PDF 保存**：下载的 PDF 保存在 `downloads/` 目录

## 许可证

MIT License

## 免责声明

本工具仅供学习和研究使用。请遵守相关平台的使用条款和学术规范。
