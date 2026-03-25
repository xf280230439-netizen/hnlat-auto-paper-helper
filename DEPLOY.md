# HNLAT 自动文献下载器 - 部署指南

## 部署方式概览

1. **本地部署** - 直接在电脑/服务器上运行
2. **Docker 部署** - 使用容器化部署
3. **云服务器部署** - 部署到 VPS/云主机
4. **Railway/Render 部署** - 使用 PaaS 平台

---

## 方式一：本地部署

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/hnlat-paper-downloader.git
cd hnlat-paper-downloader
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置账号

```bash
cp config.example.json config.json
# 编辑 config.json 填入你的账号信息
```

### 4. 运行

```bash
# 命令行模式
python hnlat_auto.py --doi 10.1038/s41586-024-08329-5

# API服务模式
python api_server.py

# Telegram Bot模式
export TELEGRAM_BOT_TOKEN="your_bot_token"
python telegram_bot.py
```

---

## 方式二：Docker 部署

### 1. 构建镜像

```bash
docker build -t hnlat-downloader .
```

### 2. 运行容器

```bash
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/downloads:/app/downloads \
  --name hnlat \
  hnlat-downloader
```

### 或使用 docker-compose

```bash
docker-compose up -d
```

---

## 方式三：云服务器部署（Ubuntu）

### 1. 准备服务器

购买一台 VPS（推荐阿里云、腾讯云、AWS、DigitalOcean 等），系统选择 Ubuntu 20.04/22.04。

### 2. 连接服务器

```bash
ssh root@your-server-ip
```

### 3. 安装依赖

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Python 和 pip
apt install -y python3 python3-pip git

# 克隆仓库
git clone https://github.com/yourusername/hnlat-paper-downloader.git
cd hnlat-paper-downloader

# 安装依赖
pip3 install -r requirements.txt
```

### 4. 配置

```bash
cp config.example.json config.json
nano config.json  # 编辑配置
```

### 5. 使用 systemd 管理服务

```bash
# 复制服务文件
cp hnlat.service /etc/systemd/system/

# 修改服务文件中的路径
nano /etc/systemd/system/hnlat.service
```

修改以下内容：
```ini
WorkingDirectory=/root/hnlat-paper-downloader  # 你的实际路径
ExecStart=/usr/bin/python3 /root/hnlat-paper-downloader/api_server.py
```

启动服务：
```bash
systemctl daemon-reload
systemctl enable hnlat
systemctl start hnlat

# 查看状态
systemctl status hnlat

# 查看日志
journalctl -u hnlat -f
```

### 6. 配置 Nginx 反向代理（可选）

```bash
apt install -y nginx
```

创建配置文件：
```bash
nano /etc/nginx/sites-available/hnlat
```

添加：
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

启用：
```bash
ln -s /etc/nginx/sites-available/hnlat /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

---

## 方式四：Railway 部署

### 1. 准备

- 注册 [Railway](https://railway.app) 账号
- 安装 Railway CLI（可选）

### 2. 部署

#### 方法一：通过 GitHub 部署

1. Fork 本仓库到你的 GitHub
2. 在 Railway  dashboard 点击 "New Project"
3. 选择 "Deploy from GitHub repo"
4. 选择你的仓库
5. 添加环境变量（在 Variables 标签页）：
   - `HNLAT_USERNAME`
   - `HNLAT_PASSWORD`
   - `QQ_EMAIL`
   - `QQ_IMAP_AUTH`
6. 部署完成！

#### 方法二：使用 CLI

```bash
# 登录
railway login

# 进入项目目录
cd hnlat-paper-downloader

# 初始化项目
railway init

# 添加环境变量
railway variables set HNLAT_USERNAME="your_username"
railway variables set HNLAT_PASSWORD="your_password"
railway variables set QQ_EMAIL="your_email"
railway variables set QQ_IMAP_AUTH="your_auth_code"

# 部署
railway up
```

---

## 方式五：Render 部署

### 1. 准备

- 注册 [Render](https://render.com) 账号
- Fork 本仓库到你的 GitHub

### 2. 创建 Web Service

1. 在 Render Dashboard 点击 "New +" → "Web Service"
2. 连接你的 GitHub 仓库
3. 配置：
   - **Name**: hnlat-downloader
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python api_server.py`
4. 添加环境变量：
   - `HNLAT_USERNAME`
   - `HNLAT_PASSWORD`
   - `QQ_EMAIL`
   - `QQ_IMAP_AUTH`
5. 点击 "Create Web Service"

---

## 与手机互动的方式

### 方案 1：Telegram Bot（推荐）

部署后，你可以通过手机上的 Telegram 随时随地控制文献下载：

1. 按照上面的方式部署服务
2. 通过 @BotFather 创建 Telegram Bot，获取 token
3. 设置环境变量 `TELEGRAM_BOT_TOKEN`
4. 运行 `python telegram_bot.py`
5. 在手机上使用 Telegram 与机器人交互

支持的命令：
- `/doi <DOI>` - 提交DOI下载
- `/title <标题>` - 按标题下载
- `/parse <公众号URL>` - 解析公众号文章
- `/status` - 查看状态

### 方案 2：API + 手机快捷指令

如果你使用 iPhone，可以创建快捷指令：

1. 部署 API 服务
2. 创建 iOS 快捷指令，调用 API
3. 可以通过分享菜单直接发送公众号链接

快捷指令示例：
- URL: `https://your-server.com/parse_wechat`
- Method: POST
- Request Body: `{"url": "[剪贴板内容]", "auto_submit": true}`

### 方案 3：Webhook + 企业微信/钉钉

可以配置企业微信或钉钉的 webhook，实现类似的效果。

---

## 安全建议

1. **不要在代码中硬编码密码**，使用环境变量或配置文件
2. **使用 HTTPS**，特别是在公网部署时
3. **限制访问**，可以通过防火墙或 Nginx 配置 IP 白名单
4. **定期更换密码**
5. **config.json 已添加到 .gitignore**，不会意外提交到 Git

---

## 故障排除

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

## 更新

```bash
cd hnlat-paper-downloader
git pull
pip install -r requirements.txt

# 如果使用 systemd
systemctl restart hnlat

# 如果使用 Docker
docker-compose down
docker-compose up -d
```
