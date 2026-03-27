import fitz  # PyMuPDF
import os
from pathlib import Path

download_dir = Path(__file__).parent / 'downloads'
pdfs = list(download_dir.glob('*.pdf'))

print("提取 PDF 摘要...\n")

for pdf_path in sorted(pdfs):
    try:
        doc = fitz.open(pdf_path)
        
        # 提取前两页文本
        text = ""
        for i in range(min(2, len(doc))):
            text += doc[i].get_text()
        
        # 查找摘要
        abstract = ""
        lines = text.split('\n')
        in_abstract = False
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if 'abstract' in line_lower or 'summary' in line_lower:
                in_abstract = True
                continue
            if in_abstract:
                if line_lower.startswith('introduction') or line_lower.startswith('keywords') or line_lower.startswith('background'):
                    break
                abstract += line + " "
                if len(abstract) > 800:
                    break
        
        doc.close()
        
        print(f"=== {pdf_path.name} ===")
        print(f"摘要: {abstract[:500]}...")
        print()
        
    except Exception as e:
        print(f"=== {pdf_path.name} ===")
        print(f"错误: {e}\n")
