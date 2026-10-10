$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $docPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EduMatrix_Project_Abstract.docx"
    $doc = $word.Documents.Open($docPath)
    $pages = $doc.ComputeStatistics(2)
    Write-Host "DOCX Page Count: $pages"
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
}
