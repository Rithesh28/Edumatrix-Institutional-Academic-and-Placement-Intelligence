$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $docxPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EduMatrix_Conference_Abstract_2026.docx"
    $pdfPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EduMatrix_Conference_Abstract_2026.pdf"
    $doc = $word.Documents.Open($docxPath)
    $pages = $doc.ComputeStatistics(2)
    Write-Host "CONFERENCE DOCX Page Count: $pages"
    $wdFormatPDF = 17
    $doc.SaveAs([ref]$pdfPath, [ref]$wdFormatPDF)
    Write-Host "PDF created successfully at $pdfPath"
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
}
