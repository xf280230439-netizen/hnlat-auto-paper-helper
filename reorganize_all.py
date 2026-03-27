import shutil
from pathlib import Path
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

download_dir = Path(__file__).parent / 'downloads'

# 先把所有PDF移动回根目录
for pdf in download_dir.rglob('*.pdf'):
    target = download_dir / pdf.name
    if pdf != target:
        shutil.move(str(pdf), str(target))

# 删除所有子目录
for d in list(download_dir.iterdir()):
    if d.is_dir():
        shutil.rmtree(str(d), ignore_errors=True)

# 重新分类
categories = {
    "01_肠道菌群与代谢": [
        "1_Gut_microbiota.pdf",
        "10_Imbalance_gut.pdf", 
        "8_Roseburia.pdf",
        "Multi-omic profiling reveals distinct gut microbia.pdf",
    ],
    "02_肠-肝轴与肠道干细胞": [
        "2_Gut_liver_axis.pdf",
        "Gut-liver axis calibrates intestinal stem cell fit.pdf",
    ],
    "03_肠-皮轴与皮肤健康": [
        "7_Dermal_injury.pdf",
        "9_Gut_skin_axis.pdf",
        "The gut-skin axis_ Emerging insights in understand.pdf",
        "The gut-skin axis_ a bi-directional, microbiota-dr.pdf",
    ],
    "04_衰老与抗衰老机制": [
        "11_Lithocholic_acid.pdf",
    ],
    "05_肿瘤免疫": [
        "3_Oxidative_stress.pdf",
        "Oxidative-stress-induced telomere instability driv.pdf",
    ],
    "06_微生物群落生态": [
        "5_Predator_microbial.pdf",
        "Predator-mediated local convergence fosters global.pdf",
    ],
    "07_人工智能与微生物组": [
        "6_Machine_learning.pdf",
    ],
    "08_大型队列与精准医学": [
        "4_Deep_phenotyping.pdf",
    ],
    "09_G蛋白偶联受体": [
        "Evolutionary study and structural basis of proton .pdf",
    ],
}

print('重新分类整理文献...\n')

total = 0
for category, files in categories.items():
    category_dir = download_dir / category
    category_dir.mkdir(exist_ok=True)
    
    moved = 0
    for f in files:
        src = download_dir / f
        if src.exists():
            dst = category_dir / f
            shutil.move(str(src), str(dst))
            moved += 1
            total += 1
    
    if moved > 0:
        print(f'[{category}] {moved} 篇')

print(f'\n总计: {total} 篇文献')

# 显示最终结构
print('\n' + '='*50)
print('文献库目录结构:')
print('='*50)

for item in sorted(download_dir.iterdir()):
    if item.is_dir():
        pdfs = sorted(item.glob('*.pdf'))
        print(f'\n{item.name}/ ({len(pdfs)} 篇)')
        for pdf in pdfs:
            size_kb = pdf.stat().st_size / 1024
            print(f'  - {pdf.name} ({size_kb:.0f} KB)')
