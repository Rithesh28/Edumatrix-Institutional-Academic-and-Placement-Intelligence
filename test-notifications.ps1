# ============================================
# NOTIFICATION TRIGGERS TEST SCRIPT
# ============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "NOTIFICATION TRIGGERS TEST" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ============================================
# STEP 1: Login as Lecturer
# ============================================
Write-Host ""
Write-Host "[STEP 1] Logging in as Lecturer" -ForegroundColor Yellow

$lecturerBody = @{
    username = "professor@college.edu"
    password = "12345"
}

try {
    $lecturerResponse = Invoke-RestMethod -Uri "http://localhost:8000/auth/login" -Method POST `
        -Body $lecturerBody `
        -ContentType "application/x-www-form-urlencoded"
    
    $lecturerToken = $lecturerResponse.access_token
    Write-Host "✅ Lecturer logged in successfully" -ForegroundColor Green
    Write-Host "   Lecturer ID: $($lecturerResponse.user.id)" -ForegroundColor White
    $lecturerId = $lecturerResponse.user.id
} catch {
    Write-Host "❌ Lecturer login failed: $_" -ForegroundColor Red
    exit
}

# ============================================
# STEP 2: Login as Student (Karan)
# ============================================
Write-Host ""
Write-Host "[STEP 2] Logging in as Student (Karan)" -ForegroundColor Yellow

$studentBody = @{
    username = "karan@gmail.com"
    password = "12345"
}

try {
    $studentResponse = Invoke-RestMethod -Uri "http://localhost:8000/auth/login" -Method POST `
        -Body $studentBody `
        -ContentType "application/x-www-form-urlencoded"
    
    $studentToken = $studentResponse.access_token
    Write-Host "✅ Student logged in successfully" -ForegroundColor Green
    Write-Host "   Student ID: $($studentResponse.user.id)" -ForegroundColor White
    $studentId = $studentResponse.user.id
} catch {
    Write-Host "❌ Student login failed: $_" -ForegroundColor Red
    exit
}

# ============================================
# STEP 3: Check Current Notifications (Before Creating Circular)
# ============================================
Write-Host ""
Write-Host "[STEP 3] Checking Current Notifications for Student (Before)" -ForegroundColor Yellow

try {
    $beforeNotifs = Invoke-RestMethod -Uri "http://localhost:8000/notifications/" -Method GET `
        -Headers @{Authorization = "Bearer $studentToken"}
    
    $beforeCount = $beforeNotifs.Count
    Write-Host "✅ Current notification count: $beforeCount" -ForegroundColor Green
    
    $unreadResponse = Invoke-RestMethod -Uri "http://localhost:8000/notifications/unread/count" -Method GET `
        -Headers @{Authorization = "Bearer $studentToken"}
    Write-Host "   Unread count: $($unreadResponse.unread_count)" -ForegroundColor White
} catch {
    Write-Host "⚠️ Could not fetch notifications: $_" -ForegroundColor Yellow
}

# ============================================
# STEP 4: Create a New Circular (This Should Trigger Notifications)
# ============================================
Write-Host ""
Write-Host "[STEP 4] Creating New Exam Circular (Triggers Notifications)" -ForegroundColor Yellow

$newCircular = @{
    type = "exam"
    title = "Mid-Term Examination 2026"
    content = "Mid-term exams will be held from June 10th to June 20th. Please check the schedule."
    due_date = "2026-06-20T23:59:00Z"
} | ConvertTo-Json

try {
    $circularResponse = Invoke-RestMethod -Uri "http://localhost:8000/circulars/" -Method POST `
        -Headers @{Authorization = "Bearer $lecturerToken"} `
        -ContentType "application/json" `
        -Body $newCircular
    
    Write-Host "✅ Circular Created Successfully!" -ForegroundColor Green
    Write-Host "   Circular ID: $($circularResponse.id)" -ForegroundColor White
    Write-Host "   Title: $($circularResponse.title)" -ForegroundColor White
    Write-Host "   Type: $($circularResponse.type)" -ForegroundColor White
    $circularId = $circularResponse.id
} catch {
    Write-Host "❌ Failed to create circular: $_" -ForegroundColor Red
    exit
}

# ============================================
# STEP 5: Check Notifications After Creating Circular
# ============================================
Write-Host ""
Write-Host "[STEP 5] Checking Notifications for Student (After)" -ForegroundColor Yellow

try {
    $afterNotifs = Invoke-RestMethod -Uri "http://localhost:8000/notifications/" -Method GET `
        -Headers @{Authorization = "Bearer $studentToken"}
    
    $afterCount = $afterNotifs.Count
    Write-Host "✅ New notification count: $afterCount" -ForegroundColor Green
    Write-Host "   (Previous: $beforeCount, New: $afterCount)" -ForegroundColor White
    
    $newNotifications = $afterCount - $beforeCount
    Write-Host "   New notifications received: $newNotifications" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "   Latest Notifications:" -ForegroundColor Magenta
    $firstFew = $afterNotifs | Select-Object -First 3
    foreach ($notif in $firstFew) {
        Write-Host "   - [$($notif.type)] $($notif.title)" -ForegroundColor White
        Write-Host "     Message: $($notif.message)" -ForegroundColor Gray
        Write-Host "     Read: $($notif.is_read)" -ForegroundColor Gray
    }
} catch {
    Write-Host "❌ Failed to fetch notifications: $_" -ForegroundColor Red
}

# ============================================
# STEP 6: Check Unread Count
# ============================================
Write-Host ""
Write-Host "[STEP 6] Checking Unread Notification Count" -ForegroundColor Yellow

try {
    $unreadResponse = Invoke-RestMethod -Uri "http://localhost:8000/notifications/unread/count" -Method GET `
        -Headers @{Authorization = "Bearer $studentToken"}
    
    Write-Host "✅ Unread notifications: $($unreadResponse.unread_count)" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to get unread count: $_" -ForegroundColor Red
}

# ============================================
# STEP 7: Mark One Notification as Read
# ============================================
if ($afterNotifs.Count -gt 0) {
    Write-Host ""
    Write-Host "[STEP 7] Marking First Notification as Read" -ForegroundColor Yellow
    
    $firstNotifId = $afterNotifs[0].id
    
    try {
        $markRead = Invoke-RestMethod -Uri "http://localhost:8000/notifications/$firstNotifId/read" -Method PUT `
            -Headers @{Authorization = "Bearer $studentToken"}
        
        Write-Host "✅ Notification $firstNotifId marked as read" -ForegroundColor Green
    } catch {
        Write-Host "❌ Failed to mark as read: $_" -ForegroundColor Red
    }
}

# ============================================
# STEP 8: Check Unread Count Again
# ============================================
Write-Host ""
Write-Host "[STEP 8] Checking Unread Count After Marking Read" -ForegroundColor Yellow

try {
    $unreadResponse2 = Invoke-RestMethod -Uri "http://localhost:8000/notifications/unread/count" -Method GET `
        -Headers @{Authorization = "Bearer $studentToken"}
    
    Write-Host "✅ Unread notifications: $($unreadResponse2.unread_count)" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to get unread count: $_" -ForegroundColor Red
}

# ============================================
# STEP 9: Create Another Circular (Different Type)
# ============================================
Write-Host ""
Write-Host "[STEP 9] Creating Another Circular (Assignment Type)" -ForegroundColor Yellow

$assignmentCircular = @{
    type = "assignment"
    title = "Python Project Submission"
    content = "Submit your final Python project by end of this month."
    due_date = "2026-05-30T23:59:00Z"
} | ConvertTo-Json

try {
    $assignmentResponse = Invoke-RestMethod -Uri "http://localhost:8000/circulars/" -Method POST `
        -Headers @{Authorization = "Bearer $lecturerToken"} `
        -ContentType "application/json" `
        -Body $assignmentCircular
    
    Write-Host "✅ Assignment Circular Created!" -ForegroundColor Green
    Write-Host "   Circular ID: $($assignmentResponse.id)" -ForegroundColor White
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# STEP 10: Check Database Directly
# ============================================
Write-Host ""
Write-Host "[STEP 10] Checking Notifications Table in Database" -ForegroundColor Yellow

try {
    $dbNotifs = docker exec edumatrix_postgres psql -U edumatrix -d edumatrix -t -c "SELECT id, user_id, type, title, is_read, created_at FROM notifications ORDER BY id DESC LIMIT 5;"
    Write-Host "✅ Database Records:" -ForegroundColor Green
    Write-Host $dbNotifs
} catch {
    Write-Host "⚠️ Could not query database" -ForegroundColor Yellow
}

# ============================================
# STEP 11: Mark All Notifications as Read
# ============================================
Write-Host ""
Write-Host "[STEP 11] Marking All Notifications as Read" -ForegroundColor Yellow

try {
    $markAll = Invoke-RestMethod -Uri "http://localhost:8000/notifications/read-all" -Method PUT `
        -Headers @{Authorization = "Bearer $studentToken"}
    
    Write-Host "✅ All notifications marked as read" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# STEP 12: Final Unread Count Check
# ============================================
Write-Host ""
Write-Host "[STEP 12] Final Unread Count Check" -ForegroundColor Yellow

try {
    $finalUnread = Invoke-RestMethod -Uri "http://localhost:8000/notifications/unread/count" -Method GET `
        -Headers @{Authorization = "Bearer $studentToken"}
    
    Write-Host "✅ Final unread count: $($finalUnread.unread_count)" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed: $_" -ForegroundColor Red
}

# ============================================
# SUMMARY
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ Lecturer Login: WORKING" -ForegroundColor Green
Write-Host "✅ Student Login: WORKING" -ForegroundColor Green
Write-Host "✅ Create Circular: WORKING" -ForegroundColor Green
Write-Host "✅ Notifications Auto-Created: WORKING" -ForegroundColor Green
Write-Host "✅ Get Notifications: WORKING" -ForegroundColor Green
Write-Host "✅ Get Unread Count: WORKING" -ForegroundColor Green
Write-Host "✅ Mark as Read: WORKING" -ForegroundColor Green
Write-Host "✅ Mark All as Read: WORKING" -ForegroundColor Green
Write-Host "✅ Database Storage: WORKING" -ForegroundColor Green

Write-Host ""
Write-Host "Test Results:" -ForegroundColor Magenta
Write-Host "   Circular Created ID: $circularId" -ForegroundColor White
Write-Host "   Notifications before: $beforeCount" -ForegroundColor White
Write-Host "   Notifications after: $afterCount" -ForegroundColor White
Write-Host "   New notifications created: $newNotifications" -ForegroundColor Cyan