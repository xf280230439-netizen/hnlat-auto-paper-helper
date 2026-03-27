import shutil
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

download_dir = Path(__file__).parent / 'downloads'

categories = {
    "01_肠道菌群与代谢": [
        "Multi-omic profiling reveals distinct gut microbia.pdf",  # 金丝猴多组学 - npj Biofilms
    ],
    "02_肠-肝轴与肠道干细胞": [
        "Gut-liver axis calibrates intestinal stem cell fit.pdf",
    ],
    "03_肠-皮轴与皮肤健康": [
        "The gut-skin axis_ Emerging insights in understand.pdf",  # IJMM 综述
        "The gut-skin axis_ a bi-directional, microbiota-dr.pdf",  # Gut Microbes
    ],
    "05_肿瘤免疫": [
        "Oxidative-stress-induced telomere instability driv.pdf",
    ],
    "06_微生物群落生态": [
        "Predator-mirobial.pdf",  # 文件名可能有差异
    ],
    "09_G蛋白偶联受体与进化": [
        "Evolutionary study and structural basis of proton sensing by Mus GPR4 and Xenopus GPR4.pdf",
    ],
}

print('整理新下载的文献...\n')

for category, files in categories.items():
    category_dir = download_dir / category
    category_dir.mkdir(exist_ok=True)
    print(f'[{category}]')
    
    for f in files:
        src = download_dir / f
        # 模糊匹配
        if not src.exists():
            candidates = list(download_dir.glob(f'*GPR4*'))
            if candidates:
                src = candidates[0]
        
        if src.exists():
            dst = category_dir / src.name
            shutil.move(str(src), str(dst))
            print(f'  -> {src.name}')
        else:
            print(f'  [未找到] {f}')
    print()

# 处理文件名差异
predator_candidates = list(download_dir.glob('*Predator*'))
if predator_candidates:
    cat_dir = download_dir / '06_微生物群落生态'
    cat_dir.mkdir(exist_ok=True)
    for p in predator_candidates:
        shutil.move(str(p), str(cat_dir / p.name))
        print(f'[06] -> {p.name}')

# 显示最终结果
print('\n最终目录结构:')
for item in sorted(download_dir.iterdir()):
    if item.is_dir():
        pdfs = list(item.glob('*.pdf'))
        print(f'  {item.name}/ ({len(pdfs)} 篇)')
