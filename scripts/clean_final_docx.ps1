$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $path = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Research_Paper_Updated.docx"
    $doc = $word.Documents.Open($path)
    
    # Check headers and shapes
    foreach ($section in $doc.Sections) {
        $header = $section.Headers.Item(1) # wdHeaderFooterPrimary
        $range = $header.Range
        $find = $range.Find
        $find.Text = "Remove this"
        $find.Replacement.Text = ""
        $find.Execute([ref]$null, [ref]$null, [ref]$null, [ref]$null, [ref]$null, [ref]$null, [ref]$null, [ref]$null, [ref]$null, [ref]$null, [ref]2) # 2 = wdReplaceAll
        
        # Check shapes in header
        for ($i = $header.Shapes.Count; $i -ge 1; $i--) {
            $sh = $header.Shapes.Item($i)
            try {
                if ($sh.TextFrame.HasText) {
                    if ($sh.TextFrame.TextRange.Text -like "*Remove this*") {
                        Write-Host "Deleting shape with Remove this"
                        $sh.Delete()
                    }
                }
            } catch {}
        }
    }
    
    $doc.Save()
    
    # Export clean PDF as well
    $pdfPath = "d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Research_Paper_Updated.pdf"
    $doc.SaveAs2([ref]$pdfPath, [ref]17)
    Write-Host "Clean PDF exported to $pdfPath"
    
    # Copy to Downloads and Major Project-II
    Copy-Item $path "C:\Users\rithe\Downloads\EDUMATRIX_Research_Paper_Updated.docx" -Force
    Copy-Item $pdfPath "C:\Users\rithe\Downloads\EDUMATRIX_Research_Paper_Updated.pdf" -Force
    Copy-Item $path "D:\7th sem\Major Project-II\EDUMATRIX_Research_Paper_Updated.docx" -Force
    Write-Host "All files updated and copied!"
    
    $doc.Close([ref]$false)
} catch {
    Write-Host "Error: $_"
} finally {
    $word.Quit()
}
