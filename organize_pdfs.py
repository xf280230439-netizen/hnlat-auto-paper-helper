import shutil
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

download_dir = Path(__file__).parent / 'downloads'

# 分类规则
categories = {
    "01_肠道菌群与代谢": [
        "1_Gut_microbiota.pdf",
        "10_Imbalance_gut.pdf",
        "8_Roseburia.pdf",
    ],
    "02_肠-肝轴与肠道干细胞": [
        "2_Gut_liver_axis.pdf",
    ],
    "03_肠-皮轴与皮肤健康": [
        "7_Dermal_injury.pdf",
        "9_Gut_skin_axis.pdf",
    ],
    "04_衰老与抗衰老机制": [
        "11_Lithocholic_acid.pdf",
    ],
    "05_肿瘤免疫": [
        "3_Oxidative_stress.pdf",
    ],
    "06_微生物群落生态": [
        "5_Predator_microbial.pdf",
    ],
    "07_人工智能与微生物组": [
        "6_Machine_learning.pdf",
    ],
    "08_大型队列与精准医学": [
        "4_Deep_phenotyping.pdf",
    ],
}

print("创建分类文件夹并移动文件...\n")

for category, files in categories.items():
    category_dir = download_dir / category
    category_dir.mkdir(exist_ok=True)
    
    print(f"[{category}]")
    for f in files:
        src = download_dir / f
        if src.exists():
            dst = category_dir / f
            shutil.move(str(src), str(dst))
            print(f"   -> {f}")
        else:
            print(f"   [未找到] {f}")
    print()

print("\n分类完成！")
print(f"\n目录结构:")
for item in sorted(download_dir.iterdir()):
    if item.is_dir():
        pdfs = list(item.glob("*.pdf"))
        print(f"  {item.name}/ ({len(pdfs)} 篇)")
        for pdf in pdfs:
            print(f"    - {pdf.name}")
