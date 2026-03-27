import asyncio
from playwright.async_api import async_playwright
import sys
import os
from pathlib import Path

# 下载链接列表
links = [
    ("1_Gut_microbiota_short_chain_fatty_acids", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22152757&_gri=26072176&c=014F7EB65253A6C9"),
    ("2_Gut_liver_axis_intestinal_stem_cell", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151506&_gri=26071615&c=2D6E880EF7BFE5C3"),
    ("3_Oxidative_stress_telomere_T_cell", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151815&_gri=26071093&c=8C48A458C949AED3"),
    ("4_Deep_phenotyping_Human_Phenotype_Project", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151878&_gri=26071189&c=9A5949E69B360E92"),
    ("5_Predator_microbial_community_divergence", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151848&_gri=26071294&c=D26921C43322973F"),
    ("6_Machine_learning_microbial_pesticides", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151854&_gri=26071222&c=E836F2E5E9FB7EB7"),
    ("7_Dermal_injury_skin_gut_axis", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151803&_gri=26071078&c=3D300E822C1244E1"),
    ("8_Roseburia_inulinivorans_muscle_strength", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151800&_gri=26071069&c=7DC848704057927F"),
    ("9_Gut_skin_axis_bi_directional", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151821&_gri=26071105&c=539A93C873A744FB"),
    ("10_Imbalance_gut_microbial_interactions", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151779&_gri=26071048&c=3FF6EC39BDE9F85E"),
    ("11_Lithocholic_acid_anti_ageing", "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=21882727&_gri=25750072&c=40087A63C82DEEB7"),
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
            print(f"\n[{i}/{len(links)}] 下载: {title}...")
            
            try:
                await page.goto(url, wait_until='networkidle')
                await page.wait_for_timeout(3000)
                
                # 查找下载按钮
                download_btn = await page.query_selector('button:has-text("下载"), a:has-text("下载"), .download, .btn-download, [class*="down"]')
                
                if download_btn:
                    async with page.expect_download(timeout=60000) as download_info:
                        await download_btn.click()
                        download = await download_info.value
                        
                        filename = f"{title}.pdf"
                        filepath = download_dir / filename
                        await download.save_as(filepath)
                        print(f"  ✅ 已保存: {filename}")
                        downloaded.append(filename)
                else:
                    # 截图查看页面结构
                    await page.screenshot(path=str(download_dir / f'{title}_page.png'))
                    print(f"  ❌ 未找到下载按钮，已截图保存")
                        
            except Exception as e:
                print(f"  ❌ 错误: {e}")
                try:
                    await page.screenshot(path=str(download_dir / f'{title}_error.png'))
                except:
                    pass
        
        await browser.close()
        
        print(f"\n✅ 共下载 {len(downloaded)} 个 PDF")
        return downloaded

if __name__ == "__main__":
    asyncio.run(download_pdfs())
