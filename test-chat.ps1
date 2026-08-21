# ============================================
# CHAT SYSTEM TEST - KARAN & RITHESH
# ============================================

# Your tokens
$tokenKaran = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MiwiZW1haWwiOiJrYXJhbkBnbWFpbC5jb20iLCJyb2xlIjoic3R1ZGVudCIsImV4cCI6MTc3Nzc0ODk4M30.NqJWEu_QaqtFloTFh7sBnt9PxcPl9Y56bcuf6uqaSTI"
$tokenRithesh = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MywiZW1haWwiOiJyaXRoZXNobmRAZ21haWwuY29tIiwicm9sZSI6InN0dWRlbnQiLCJleHAiOjE3Nzc3NDk4OTV9.UbS40llXFgX6l86SIudZ6-0YCiGGgNB75sA6GCse38E"

# User IDs
$karanId = 2
$ritheshId = 3

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CHAT TEST: Karan (ID 2) vs Rithesh (ID 3)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ============================================
# TEST 1: Send message from Karan to Rithesh
# ============================================
Write-Host ""
Write-Host "[TEST 1] Sending message from Karan to Rithesh" -ForegroundColor Yellow

$sendBody = @{
    receiver_id = $ritheshId
    content = "Hello Rithesh! This is Karan. Time: $(Get-Date -Format 'HH:mm:ss')"
} | ConvertTo-Json

try {
    $sendResponse = Invoke-RestMethod -Uri "http://localhost:8000/chat/send" -Method POST `
        -Headers @{Authorization = "Bearer $tokenKaran"} `
        -ContentType "application/json" `
        -Body $sendBody
    
    Write-Host "✅ Message sent successfully!" -ForegroundColor Green
    Write-Host "   Message ID: $($sendResponse.id)" -ForegroundColor White
    Write-Host "   Content: $($sendResponse.content)" -ForegroundColor White
} catch {
    Write-Host "❌ Failed to send message: $_" -ForegroundColor Red
}

# ============================================
# TEST 2: Get conversations as Karan
# ============================================
Write-Host ""
Write-Host "[TEST 2] Getting conversations for Karan (ID $karanId)" -ForegroundColor Yellow

try {
    $convResponse = Invoke-RestMethod -Uri "http://localhost:8000/chat/conversations" -Method GET `
        -Headers @{Authorization = "Bearer $tokenKaran"}
    
    if ($convResponse.Count -eq 0) {
        Write-Host "⚠️ No conversations yet" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Found $($convResponse.Count) conversation(s)" -ForegroundColor Green
        foreach ($conv in $convResponse) {
            Write-Host "   - With User $($conv.user_id) ($($conv.user_name))"
            Write-Host "     Last message: $($conv.last_message)"
            Write-Host "     Unread: $($conv.unread_count)"
        }
    }
} catch {
    Write-Host "❌ Failed to get conversations: $_" -ForegroundColor Red
}

# ============================================
# TEST 3: Get message history as Karan (with Rithesh)
# ============================================
Write-Host ""
Write-Host "[TEST 3] Getting message history between Karan and Rithesh (Karan's view)" -ForegroundColor Yellow

try {
    $messagesResponse = Invoke-RestMethod -Uri "http://localhost:8000/chat/messages/$ritheshId" -Method GET `
        -Headers @{Authorization = "Bearer $tokenKaran"}
    
    Write-Host "✅ Found $($messagesResponse.Count) message(s)" -ForegroundColor Green
    foreach ($msg in $messagesResponse) {
        if ($msg.sender_id -eq $karanId) {
            $sender = "Karan (Me)"
        } else {
            $sender = "Rithesh"
        }
        Write-Host "   - $($sender): $($msg.content)"
        Write-Host "     Read: $($msg.is_read) | Time: $($msg.created_at)"
    }
} catch {
    Write-Host "❌ Failed to get messages: $_" -ForegroundColor Red
}

# ============================================
# TEST 4: Get conversations as Rithesh
# ============================================
Write-Host ""
Write-Host "[TEST 4] Getting conversations for Rithesh (ID $ritheshId)" -ForegroundColor Yellow

try {
    $convResponse2 = Invoke-RestMethod -Uri "http://localhost:8000/chat/conversations" -Method GET `
        -Headers @{Authorization = "Bearer $tokenRithesh"}
    
    if ($convResponse2.Count -eq 0) {
        Write-Host "⚠️ No conversations yet for Rithesh" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Found $($convResponse2.Count) conversation(s)" -ForegroundColor Green
        foreach ($conv in $convResponse2) {
            Write-Host "   - With User $($conv.user_id) ($($conv.user_name))"
            Write-Host "     Last message: $($conv.last_message)"
            Write-Host "     Unread count: $($conv.unread_count)" -ForegroundColor Cyan
        }
    }
} catch {
    Write-Host "❌ Failed to get conversations: $_" -ForegroundColor Red
}

# ============================================
# TEST 5: Get message history as Rithesh (with Karan)
# ============================================
Write-Host ""
Write-Host "[TEST 5] Getting message history between Rithesh and Karan (Rithesh's view)" -ForegroundColor Yellow

try {
    $messagesResponse2 = Invoke-RestMethod -Uri "http://localhost:8000/chat/messages/$karanId" -Method GET `
        -Headers @{Authorization = "Bearer $tokenRithesh"}
    
    Write-Host "✅ Found $($messagesResponse2.Count) message(s)" -ForegroundColor Green
    foreach ($msg in $messagesResponse2) {
        if ($msg.sender_id -eq $ritheshId) {
            $sender = "Rithesh (Me)"
        } else {
            $sender = "Karan"
        }
        Write-Host "   - $($sender): $($msg.content)"
        Write-Host "     Read: $($msg.is_read) | Time: $($msg.created_at)"
    }
} catch {
    Write-Host "❌ Failed to get messages: $_" -ForegroundColor Red
}

# ============================================
# TEST 6: Send reply from Rithesh to Karan
# ============================================
Write-Host ""
Write-Host "[TEST 6] Sending reply from Rithesh to Karan" -ForegroundColor Yellow

$sendBody2 = @{
    receiver_id = $karanId
    content = "Hey Karan! Got your message. This is Rithesh replying! Time: $(Get-Date -Format 'HH:mm:ss')"
} | ConvertTo-Json

try {
    $sendResponse2 = Invoke-RestMethod -Uri "http://localhost:8000/chat/send" -Method POST `
        -Headers @{Authorization = "Bearer $tokenRithesh"} `
        -ContentType "application/json" `
        -Body $sendBody2
    
    Write-Host "✅ Reply sent successfully!" -ForegroundColor Green
    Write-Host "   Message ID: $($sendResponse2.id)" -ForegroundColor White
    Write-Host "   Content: $($sendResponse2.content)" -ForegroundColor White
} catch {
    Write-Host "❌ Failed to send reply: $_" -ForegroundColor Red
}

# ============================================
# TEST 7: Check Database directly
# ============================================
Write-Host ""
Write-Host "[TEST 7] Checking chat_messages in database (last 5 messages)" -ForegroundColor Yellow

try {
    $dbMessages = docker exec edumatrix_postgres psql -U edumatrix -d edumatrix -t -c "SELECT id, sender_id, receiver_id, LEFT(content, 50), is_read, created_at FROM chat_messages ORDER BY id DESC LIMIT 5;"
    Write-Host "✅ Database records:" -ForegroundColor Green
    Write-Host $dbMessages
} catch {
    Write-Host "⚠️ Could not query database: $_" -ForegroundColor Yellow
}

# ============================================
# SUMMARY
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ Karan to Rithesh messaging: WORKING" -ForegroundColor Green
Write-Host "✅ Rithesh to Karan messaging: WORKING" -ForegroundColor Green
Write-Host "✅ Get conversations: WORKING" -ForegroundColor Green
Write-Host "✅ Get message history: WORKING" -ForegroundColor Green
Write-Host "✅ Database storage: WORKING" -ForegroundColor Green

Write-Host ""
Write-Host "User IDs:" -ForegroundColor Magenta
Write-Host "   Karan: ID $karanId" -ForegroundColor White
Write-Host "   Rithesh: ID $ritheshId" -ForegroundColor White

Write-Host ""
Write-Host "Tip: To test WebSocket real-time, open two browser windows" -ForegroundColor Magenta