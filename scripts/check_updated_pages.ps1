$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $src = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Research_Paper_Updated.docx"
    $doc = $word.Documents.Open($src, [ref]$false, [ref]$true)
    $pages = $doc.ComputeStatistics(2)
    Write-Host "Updated DOCX Page Count: $pages"
    
    # Export to PDF to see visual output
    $pdfPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Research_Paper_Updated.pdf"
    $doc.SaveAs2([ref]$pdfPath, [ref]17) # 17 = wdFormatPDF
    Write-Host "PDF exported to: $pdfPath"
    
    $doc.Close([ref]$false)
} catch {
    Write-Host "Error checking pages: $_"
} finally {
    $word.Quit()
}
