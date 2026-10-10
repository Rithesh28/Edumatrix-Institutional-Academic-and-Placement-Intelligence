$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $docxPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Human_Abstract.docx"
    $pdfPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Human_Abstract.pdf"
    $doc = $word.Documents.Open($docxPath)
    $pages = $doc.ComputeStatistics(2) # 2 = wdStatisticPages
    $words = $doc.ComputeStatistics(0) # 0 = wdStatisticWords
    $lines = $doc.ComputeStatistics(1) # 1 = wdStatisticLines
    Write-Host "PAGES: $pages"
    Write-Host "WORDS: $words"
    Write-Host "LINES: $lines"
    $wdFormatPDF = 17
    $doc.SaveAs([ref]$pdfPath, [ref]$wdFormatPDF)
    Write-Host "PDF created successfully at $pdfPath"
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
}
