$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $docxPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Abstract.docx"
    $pdfPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Abstract.pdf"
    $doc = $word.Documents.Open($docxPath)
    $pages = $doc.ComputeStatistics(2)
    Write-Host "PAGES: $pages"
    $wdFormatPDF = 17
    $doc.SaveAs([ref]$pdfPath, [ref]$wdFormatPDF)
    Write-Host "PDF created successfully at $pdfPath"
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
}
