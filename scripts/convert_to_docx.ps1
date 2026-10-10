$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $src = "C:\Users\rithe\Downloads\EDUMATRIX_Research_Paper - corrections.doc"
    $dst = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Research_Paper.docx"
    Write-Host "Opening $src..."
    $doc = $word.Documents.Open($src, [ref]$false, [ref]$true) # Open ReadOnly to avoid locks
    Write-Host "Saving to $dst..."
    $doc.SaveAs2([ref]$dst, [ref]16) # 16 = wdFormatDocumentDefault (.docx)
    $doc.Close([ref]$false)
    Write-Host "Conversion to .docx successful!"
} catch {
    Write-Host "Error during conversion: $_"
} finally {
    $word.Quit()
}
