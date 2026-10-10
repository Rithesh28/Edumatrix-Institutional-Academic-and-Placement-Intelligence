$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $docxPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EduMatrix_Project_Abstract.docx"
    $pdfPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EduMatrix_Project_Abstract.pdf"
    $doc = $word.Documents.Open($docxPath)
    $wdFormatPDF = 17
    $doc.SaveAs([ref]$pdfPath, [ref]$wdFormatPDF)
    Write-Host "PDF created successfully at $pdfPath"
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
}
