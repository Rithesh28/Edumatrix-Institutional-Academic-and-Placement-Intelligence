$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $path1 = "C:\Users\rithe\Downloads\EDUMATRIX_Research_Paper - corrections.doc"
    if (Test-Path $path1) {
        $doc = $word.Documents.Open($path1)
        Write-Host "File 1: $path1"
        Write-Host "Page Count:" $doc.ComputeStatistics(2)
        Write-Host "Tables Count:" $doc.Tables.Count
        for ($i = 1; $i -le $doc.Tables.Count; $i++) {
            $t = $doc.Tables.Item($i)
            Write-Host "Table $i - Rows:" $t.Rows.Count "Cols:" $t.Columns.Count
        }
        $doc.Close([ref]$false)
    }

    $path2 = "D:\7th sem\Major Project-II\EDUMATRIX_Research_Paper.doc"
    if (Test-Path $path2) {
        $doc2 = $word.Documents.Open($path2)
        Write-Host "File 2: $path2"
        Write-Host "Page Count:" $doc2.ComputeStatistics(2)
        Write-Host "Tables Count:" $doc2.Tables.Count
        for ($i = 1; $i -le $doc2.Tables.Count; $i++) {
            $t = $doc2.Tables.Item($i)
            Write-Host "Table $i - Rows:" $t.Rows.Count "Cols:" $t.Columns.Count
        }
        $doc2.Close([ref]$false)
    }
} catch {
    Write-Host "Error:" $_
} finally {
    $word.Quit()
}
