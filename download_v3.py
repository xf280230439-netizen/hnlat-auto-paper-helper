import asyncio
from playwright.async_api import async_playwright
import sys
import os
from pathlib import Path

# 设置 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')

# 下载链接列表
links = [
    ("1_Gut_microbiota", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22152757&_gri=26072176&c=014F7EB65253A6C9"),
    ("2_Gut_liver_axis", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151506&_gri=26071615&c=2D6E880EF7BFE5C3"),
    ("3_Oxidative_stress", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151815&_gri=26071093&c=8C48A458C949AED3"),
    ("4_Deep_phenotyping", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151878&_gri=26071189&c=9A5949E69B360E92"),
    ("5_Predator_microbial", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151848&_gri=26071294&c=D26921C43322973F"),
    ("6_Machine_learning", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151854&_gri=26071222&c=E836F2E5E9FB7EB7"),
    ("7_Dermal_injury", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151803&_gri=26071078&c=3D300E822C1244E1"),
    ("8_Roseburia", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151800&_gri=26071069&c=7DC848704057927F"),
    ("9_Gut_skin_axis", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151821&_gri=26071105&c=539A93C873A744FB"),
    ("10_Imbalance_gut", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151779&_gri=26071048&c=3FF6EC39BDE9F85E"),
    ("11_Lithocholic_acid", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=21882727&_gri=25750072&c=40087A63C82DEEB7"),
]

download_dir = Path(__file__).parent / 'downloads'
download_dir.mkdir(exist_ok=True)

async def download_pdfs():
    print("启动浏览器...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        
        downloaded = []
        
        for i, (title, url) in enumerate(links, 1):
            print(f"\n[{i}/{len(links)}] {title}...")
            
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(3000)
                
                # 截图保存页面
                screenshot_path = str(download_dir / f'{title}_page.png')
                await page.screenshot(path=screenshot_path)
                print(f"  截图已保存: {screenshot_path}")
                
                # 获取页面内容
                content = await page.content()
                html_path = str(download_dir / f'{title}_page.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  HTML已保存: {html_path}")
                
                # 查找下载按钮
                selectors = [
                    'button:has-text("下载")',
                    'a:has-text("下载")', 
                    'button:has-text("Download")',
                    'a:has-text("Download")',
                    '.download',
                    '.btn-download',
                    '[class*="down"]',
                    'input[type="button"][value*="下载"]',
                    'input[type="submit"][value*="下载"]',
                ]
                
                download_btn = None
                for sel in selectors:
                    try:
                        btn = await page.query_selector(sel)
                        if btn:
                            download_btn = btn
                            print(f"  找到按钮: {sel}")
                            break
                    except:
                        pass
                
                if download_btn:
                    try:
                        async with page.expect_download(timeout=60000) as download_info:
                            await download_btn.click()
                            download = await download_info.value
                            
                            filename = f"{title}.pdf"
                            filepath = download_dir / filename
                            await download.save_as(filepath)
                            print(f"  SUCCESS: {filename}")
                            downloaded.append(filename)
                    except Exception as e:
                        print(f"  点击下载失败: {e}")
                else:
                    print(f"  未找到下载按钮")
                        
            except Exception as e:
                print(f"  ERROR: {e}")
        
        await browser.close()
        
        print(f"\n\n共下载 {len(downloaded)} 个 PDF")
        for f in downloaded:
            print(f"  - {f}")
        return downloaded

if __name__ == "__main__":
    asyncio.run(download_pdfs())
