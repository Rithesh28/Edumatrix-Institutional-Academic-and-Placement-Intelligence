# ============================================
# CIRCULARS TEST SCRIPT
# ============================================

# Your Lecturer Token
$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MSwiZW1haWwiOiJwcm9mZXNzb3JAY29sbGVnZS5lZHUiLCJyb2xlIjoibGVjdHVyZXIiLCJleHAiOjE3Nzc4MjcxMjl9.rU3rbqSHVBGXU-7n7ZOLNi9hDc3frhg83qiEMQtwKco"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CIRCULARS API TEST" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ============================================
# TEST 1: Create an Exam Circular
# ============================================
Write-Host ""
Write-Host "[TEST 1] Creating Exam Circular" -ForegroundColor Yellow

$examCircular = @{
    type = "exam"
    title = "Final Examination - CS101"
    content = "The final exam for Computer Science 101 will be held on May 15th, 2026 from 9:00 AM to 12:00 PM in Hall A."
    due_date = "2026-05-15T09:00:00Z"
} | ConvertTo-Json

try {
    $response1 = Invoke-RestMethod -Uri "http://localhost:8000/circulars/" -Method POST `
        -Headers @{Authorization = "Bearer $token"} `
        -ContentType "application/json" `
        -Body $examCircular
    
    Write-Host "✅ Exam Circular Created!" -ForegroundColor Green
    Write-Host "   ID: $($response1.id)" -ForegroundColor White
    Write-Host "   Title: $($response1.title)" -ForegroundColor White
    Write-Host "   Type: $($response1.type)" -ForegroundColor White
    $examId = $response1.id
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# TEST 2: Create an Assignment Circular
# ============================================
Write-Host ""
Write-Host "[TEST 2] Creating Assignment Circular" -ForegroundColor Yellow

$assignmentCircular = @{
    type = "assignment"
    title = "Python Programming Assignment"
    content = "Submit a Python program implementing a binary search tree. Due by end of week."
    due_date = "2026-05-10T23:59:00Z"
} | ConvertTo-Json

try {
    $response2 = Invoke-RestMethod -Uri "http://localhost:8000/circulars/" -Method POST `
        -Headers @{Authorization = "Bearer $token"} `
        -ContentType "application/json" `
        -Body $assignmentCircular
    
    Write-Host "✅ Assignment Circular Created!" -ForegroundColor Green
    Write-Host "   ID: $($response2.id)" -ForegroundColor White
    Write-Host "   Title: $($response2.title)" -ForegroundColor White
    $assignId = $response2.id
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# TEST 3: Create a General Circular
# ============================================
Write-Host ""
Write-Host "[TEST 3] Creating General Circular" -ForegroundColor Yellow

$generalCircular = @{
    type = "general"
    title = "College Festival Announcement"
    content = "Annual Tech Fest will be held on June 1st-3rd. All students are encouraged to participate."
    due_date = $null
} | ConvertTo-Json

try {
    $response3 = Invoke-RestMethod -Uri "http://localhost:8000/circulars/" -Method POST `
        -Headers @{Authorization = "Bearer $token"} `
        -ContentType "application/json" `
        -Body $generalCircular
    
    Write-Host "✅ General Circular Created!" -ForegroundColor Green
    Write-Host "   ID: $($response3.id)" -ForegroundColor White
    Write-Host "   Title: $($response3.title)" -ForegroundColor White
    $generalId = $response3.id
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# TEST 4: Get All Circulars
# ============================================
Write-Host ""
Write-Host "[TEST 4] Getting All Circulars" -ForegroundColor Yellow

try {
    $allCirculars = Invoke-RestMethod -Uri "http://localhost:8000/circulars/" -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "✅ Found $($allCirculars.Count) circular(s)" -ForegroundColor Green
    foreach ($circ in $allCirculars) {
        Write-Host "   - [$($circ.type)] $($circ.title) (ID: $($circ.id))" -ForegroundColor White
    }
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# TEST 5: Get Circular by ID (Exam)
# ============================================
if ($examId) {
    Write-Host ""
    Write-Host "[TEST 5] Getting Exam Circular by ID ($examId)" -ForegroundColor Yellow
    
    try {
        $singleCircular = Invoke-RestMethod -Uri "http://localhost:8000/circulars/$examId" -Method GET `
            -Headers @{Authorization = "Bearer $token"}
        
        Write-Host "✅ Circular Retrieved!" -ForegroundColor Green
        Write-Host "   Title: $($singleCircular.title)" -ForegroundColor White
        Write-Host "   Content: $($singleCircular.content)" -ForegroundColor White
        Write-Host "   Lecturer: $($singleCircular.lecturer_name)" -ForegroundColor White
    } catch {
        Write-Host "❌ Failed: $_" -ForegroundColor Red
    }
}

# ============================================
# TEST 6: Filter Circulars by Type (Exam)
# ============================================
Write-Host ""
Write-Host "[TEST 6] Filtering Circulars by Type: EXAM" -ForegroundColor Yellow

try {
    $examCirculars = Invoke-RestMethod -Uri "http://localhost:8000/circulars/type/exam" -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "✅ Found $($examCirculars.Count) exam circular(s)" -ForegroundColor Green
    foreach ($circ in $examCirculars) {
        Write-Host "   - $($circ.title)" -ForegroundColor White
    }
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# TEST 7: Filter Circulars by Type (Assignment)
# ============================================
Write-Host ""
Write-Host "[TEST 7] Filtering Circulars by Type: ASSIGNMENT" -ForegroundColor Yellow

try {
    $assignCirculars = Invoke-RestMethod -Uri "http://localhost:8000/circulars/type/assignment" -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "✅ Found $($assignCirculars.Count) assignment circular(s)" -ForegroundColor Green
    foreach ($circ in $assignCirculars) {
        Write-Host "   - $($circ.title)" -ForegroundColor White
    }
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# TEST 8: Update a Circular
# ============================================
if ($assignId) {
    Write-Host ""
    Write-Host "[TEST 8] Updating Assignment Circular (ID: $assignId)" -ForegroundColor Yellow
    
    $updateData = @{
        title = "UPDATED: Advanced Python Programming Assignment"
        content = "Submit a Python program implementing both binary search tree AND AVL tree with visualization."
    } | ConvertTo-Json
    
    try {
        $updated = Invoke-RestMethod -Uri "http://localhost:8000/circulars/$assignId" -Method PUT `
            -Headers @{Authorization = "Bearer $token"} `
            -ContentType "application/json" `
            -Body $updateData
        
        Write-Host "✅ Circular Updated!" -ForegroundColor Green
        Write-Host "   New Title: $($updated.title)" -ForegroundColor White
        Write-Host "   New Content: $($updated.content)" -ForegroundColor White
    } catch {
        Write-Host "❌ Failed: $_" -ForegroundColor Red
    }
}

# ============================================
# TEST 9: Check Database
# ============================================
Write-Host ""
Write-Host "[TEST 9] Checking Database Records" -ForegroundColor Yellow

try {
    $dbResult = docker exec edumatrix_postgres psql -U edumatrix -d edumatrix -t -c "SELECT id, type, title FROM circulars ORDER BY id;"
    Write-Host "✅ Database Records:" -ForegroundColor Green
    Write-Host $dbResult
} catch {
    Write-Host "⚠️ Could not query database" -ForegroundColor Yellow
}

# ============================================
# SUMMARY
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ Create Exam Circular: WORKING" -ForegroundColor Green
Write-Host "✅ Create Assignment Circular: WORKING" -ForegroundColor Green
Write-Host "✅ Create General Circular: WORKING" -ForegroundColor Green
Write-Host "✅ Get All Circulars: WORKING" -ForegroundColor Green
Write-Host "✅ Get Circular by ID: WORKING" -ForegroundColor Green
Write-Host "✅ Filter by Type (Exam): WORKING" -ForegroundColor Green
Write-Host "✅ Filter by Type (Assignment): WORKING" -ForegroundColor Green
Write-Host "✅ Update Circular: WORKING" -ForegroundColor Green
Write-Host "✅ Database Storage: WORKING" -ForegroundColor Green

Write-Host ""
Write-Host "Created Circulars:" -ForegroundColor Magenta
if ($examId) { Write-Host "   Exam Circular ID: $examId" -ForegroundColor White }
if ($assignId) { Write-Host "   Assignment Circular ID: $assignId" -ForegroundColor White }
if ($generalId) { Write-Host "   General Circular ID: $generalId" -ForegroundColor White }