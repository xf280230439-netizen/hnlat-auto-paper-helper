# HNLAT 自动文献下载器 - 本地部署完成

## ✅ 部署状态

| 项目 | 状态 | 详情 |
|------|------|------|
| 代码克隆 | ✅ 完成 | 已从 GitHub 克隆到本地 |
| 依赖安装 | ✅ 完成 | requests, flask, python-telegram-bot 已安装 |
| 配置文件 | ✅ 完成 | config.json 已创建 |
| 下载目录 | ⏳ 待创建 | 首次运行时自动创建 |

## 📍 部署位置

```
C:\Users\xf280\.qclaw\workspace\skills\hnlat-auto-paper-helper\
```

## 🔧 下一步配置

### 1. 编辑配置文件

打开 `config.json`，填入你的账号信息：

```json
{
  "hnlat_username": "你的HNLAT账号",
  "hnlat_password": "你的HNLAT密码",
  "qq_email": "你的QQ邮箱@qq.com",
  "qq_imap_auth": "QQ邮箱授权码（16位）",
  "download_dir": "./downloads",
  "loop_interval_seconds": 300
}
```

**获取QQ邮箱授权码：**
1. 登录 QQ 邮箱网页版
2. 设置 → 账户 → 开启 IMAP/SMTP 服务
3. 生成 16 位授权码（不是登录密码）

### 2. 快速测试

```bash
# 进入项目目录
cd C:\Users\xf280\.qclaw\workspace\skills\hnlat-auto-paper-helper

# 测试单个DOI
python hnlat_auto.py --doi 10.1038/s41586-024-08329-5

# 或启动API服务
python api_server.py
```

## 📚 可用命令

```bash
# 提交单篇文献（通过 DOI）
python hnlat_auto.py --doi 10.1038/s41586-024-08329-5

# 提交单篇文献（通过标题）
python hnlat_auto.py --title "Deep learning for image recognition"

# 批量提交 DOI（需要 dois.txt 文件）
python hnlat_auto.py --doi-list dois.txt

# 检查邮箱状态
python hnlat_auto.py --monitor

# 下载所有 PDF
python hnlat_auto.py --download

# 提交后持续监控
python hnlat_auto.py --doi 10.xxx --loop

# 从公众号文章自动提取并下载
python wechat_parser.py "https://mp.weixin.qq.com/s/xxxxx"

# 启动 API 服务
python api_server.py

# 启动 Telegram Bot
python telegram_bot.py
```

## 🌐 API 服务端点

启动 `api_server.py` 后，可以通过以下端点：

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

## 📱 与手机互动

### Telegram Bot 方式（推荐）

1. 通过 @BotFather 创建 Telegram Bot，获取 token
2. 设置环境变量：`set TELEGRAM_BOT_TOKEN=your_bot_token`
3. 运行：`python telegram_bot.py`
4. 在手机 Telegram 中使用命令：
   - `/doi <DOI>` - 提交DOI下载
   - `/title <标题>` - 按标题下载
   - `/parse <公众号URL>` - 解析公众号文章
   - `/status` - 查看状态

### API + 快捷指令方式

1. 启动 API 服务：`python api_server.py`
2. 在 iPhone 快捷指令中调用 API
3. 可以通过分享菜单直接发送公众号链接

## 📝 项目文件说明

| 文件 | 说明 |
|------|------|
| `hnlat_auto.py` | 核心自动化脚本 |
| `api_server.py` | Web API 服务 |
| `telegram_bot.py` | Telegram 机器人 |
| `wechat_parser.py` | 公众号文章解析器 |
| `config.json` | 配置文件（已创建） |
| `requirements.txt` | Python 依赖 |
| `Dockerfile` | Docker 部署配置 |
| `docker-compose.yml` | Docker Compose 配置 |
| `hnlat.service` | Systemd 服务配置 |

## 🚀 进阶部署

### Docker 部署

```bash
# 构建镜像
docker build -t hnlat-downloader .

# 运行容器
docker run -d \
  -p 5000:5000 \
  -v C:\Users\xf280\.qclaw\workspace\skills\hnlat-auto-paper-helper\config.json:/app/config.json \
  -v C:\Users\xf280\.qclaw\workspace\skills\hnlat-auto-paper-helper\downloads:/app/downloads \
  --name hnlat \
  hnlat-downloader
```

### 云服务器部署

详见 `DEPLOY.md` 中的"方式三：云服务器部署"部分

## ⚠️ 安全提示

1. **不要提交 config.json** - 已添加到 .gitignore
2. **使用授权码** - QQ 邮箱使用 16 位授权码，不是登录密码
3. **定期更换密码** - 特别是在公网部署时
4. **限制访问** - 如果部署到公网，配置防火墙或 IP 白名单

## 🆘 故障排除

### 登录失败
- 检查用户名密码是否正确
- 确认账号没有被封禁
- 检查网络连接

### 邮箱连接失败
- 确认使用的是授权码，不是登录密码
- 检查 QQ 邮箱是否开启了 IMAP/SMTP 服务
- 确认邮箱地址格式正确

### 下载失败
- 检查 `downloads` 目录是否有写入权限
- 确认磁盘空间充足
- 查看日志获取详细信息

---

**部署完成时间**: 2026-03-26 06:23 GMT+8
**部署位置**: C:\Users\xf280\.qclaw\workspace\skills\hnlat-auto-paper-helper
