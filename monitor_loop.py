import time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from hnlat_auto import check_email_and_download

print("[监控启动] 每5分钟检查一次邮箱，最多等待60轮（5小时）")
for i in range(60):
    print(f"[{time.strftime('%H:%M:%S')}] 第 {i+1}/60 轮检查...", flush=True)
    result = check_email_and_download()
    new = result.get('new_downloads', 0) if result else 0
    print(f"  -> 新下载: {new} 个", flush=True)
    if new > 0:
        print("[成功] 检测到新PDF，退出监控！", flush=True)
        break
    time.sleep(300)
else:
    print("[超时] 60轮检查完毕，请手动检查", flush=True)
