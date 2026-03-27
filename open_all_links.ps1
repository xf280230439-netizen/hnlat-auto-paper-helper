# 所有 HNLAT PDF 下载链接
$links = @(
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22152757&_gri=26072176&c=014F7EB65253A6C9",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151506&_gri=26071615&c=2D6E880EF7BFE5C3",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151815&_gri=26071093&c=8C48A458C949AED3",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151878&_gri=26071189&c=9A5949E69B360E92",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151848&_gri=26071294&c=D26921C43322973F",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151854&_gri=26071222&c=E836F2E5E9FB7EB7",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151803&_gri=26071078&c=3D300E822C1244E1",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151800&_gri=26071069&c=7DC848704057927F",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151821&_gri=26071105&c=539A93C873A744FB",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=22151779&_gri=26071048&c=3FF6EC39BDE9F85E",
    "https://mail-ddp-sc102.huicece.com/delivery-give?_hri=21882727&_gri=25750072&c=40087A63C82DEEB7"
)

$titles = @(
    "1. Gut microbiota-derived short-chain fatty acids - Nature Reviews Microbiology",
    "2. Gut-liver axis calibrates intestinal stem cell fitness",
    "3. Oxidative-stress-induced telomere instability - Immunity",
    "4. Deep phenotyping of health-disease continuum - Nature Medicine",
    "5. Predator-mediated local convergence - Nature Communications",
    "6. Machine learning for microbial consortia pesticides - Trends in Biotechnology",
    "7. Dermal Injury Drives a Skin to Gut Axis - Nature Communications",
    "8. Roseburia inulinivorans increases muscle strength - GUT",
    "9. The gut-skin axis bi-directional relationship - Gut Microbes",
    "10. Imbalance in gut microbial interactions - Science",
    "11. Lithocholic acid phenocopies anti-ageing effects - Nature"
)

Write-Host "正在批量打开下载页面..." -ForegroundColor Green

for ($i = 0; $i -lt $links.Count; $i++) {
    Write-Host "[$($i+1)] $($titles[$i])"
    Start-Process $links[$i]
    Start-Sleep -Milliseconds 500
}

Write-Host "`n已打开 $($links.Count) 个下载页面" -ForegroundColor Green
Write-Host "请在浏览器中逐个点击下载按钮，PDF 会自动下载到您的下载文件夹" -ForegroundColor Yellow
