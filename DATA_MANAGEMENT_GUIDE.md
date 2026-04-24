# 🗑️ StitchFlow V2 - Complete Data Management Guide

This guide shows **ALL the ways** to clear and manage data in StitchFlow V2.

---

## 📋 Table of Contents

1. [Quick Reference](#quick-reference)
2. [Method 1: Using the Clear Database Script (Recommended)](#method-1-using-the-clear-database-script-recommended)
3. [Method 2: Using API Endpoints](#method-2-using-api-endpoints)
4. [Method 3: Direct Database Commands](#method-3-direct-database-commands)
5. [Method 4: Delete Database File](#method-4-delete-database-file)
6. [Method 5: Delete Uploaded Files](#method-5-delete-uploaded-files)
7. [Complete Reset (Everything)](#complete-reset-everything)

---

## Quick Reference

| What to Delete | Method | Command |
|----------------|--------|---------|
| **All workflows** | Script | `python clear_database.py` → Option 2 |
| **Everything** | Script | `python clear_database.py` → Option 3 |
| **View stats** | Script | `python clear_database.py` → Option 1 |
| **Single workflow** | API | `DELETE /api/v1/workflows/{id}` |
| **Database file** | Manual | Delete `stitchflow.db` |
| **Uploaded files** | Manual | Delete `uploads/` folder |

---

## Method 1: Using the Clear Database Script (Recommended)

### ✅ Best for: Most users, safe and interactive

**Step 1: Navigate to backend folder**
```cmd
cd D:\Downloads\UMHack\backend
```

**Step 2: Activate virtual environment**
```cmd
venv\Scripts\activate.bat
```

**Step 3: Run the script**
```cmd
python clear_database.py
```

**Step 4: Choose an option**

```
StitchFlow V2 - Database Management
======================================================================

What would you like to do?
  1. View database statistics
  2. Delete all workflows (keep audit log)
  3. Delete ALL data (including audit log)
  4. Exit

Enter your choice (1-4):
```

### Options Explained:

#### Option 1: View Database Statistics
- Shows how many records are in each table
- **Does NOT delete anything**
- Safe to run anytime

**Example output:**
```
Current database contents:
  📊 Workflows: 26
  📊 Reasoning Results: 15
  📊 Policy Screening Results: 10
  📊 Decisions: 5
  📊 Audit Log Entries: 150
  📊 Policy Rules: 12
```

#### Option 2: Delete All Workflows (Keep Audit Log)
- Deletes all workflows
- Deletes reasoning results
- Deletes policy screening results
- Deletes decisions
- **KEEPS audit log entries** (for compliance)
- **KEEPS policy rules**

**What gets deleted:**
- ✅ All workflows
- ✅ All reasoning results
- ✅ All policy screening results
- ✅ All decisions
- ❌ Audit log (kept)
- ❌ Policy rules (kept)

#### Option 3: Delete ALL Data (Including Audit Log)
- Deletes **EVERYTHING** except policy rules
- Most thorough cleanup
- Fresh start

**What gets deleted:**
- ✅ All workflows
- ✅ All reasoning results
- ✅ All policy screening results
- ✅ All decisions
- ✅ All audit log entries
- ❌ Policy rules (kept)

---

## Method 2: Using API Endpoints

### ✅ Best for: Programmatic deletion, automation

### A. Delete Single Workflow

**Using PowerShell:**
```powershell
$workflowId = "your-workflow-id-here"
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows/$workflowId" -Method DELETE
```

**Using curl (if installed):**
```bash
curl -X DELETE http://localhost:8000/api/v1/workflows/{workflow_id}
```

**Using Python:**
```python
import requests

workflow_id = "your-workflow-id-here"
response = requests.delete(f"http://localhost:8000/api/v1/workflows/{workflow_id}")
print(response.json())
```

### B. Delete Multiple Workflows

**PowerShell script to delete all workflows:**
```powershell
# Get all workflows
$workflows = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows?limit=100"

# Delete each one
foreach ($workflow in $workflows.workflows) {
    $id = $workflow.workflow_id
    Write-Host "Deleting workflow: $id"
    Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows/$id" -Method DELETE
}

Write-Host "All workflows deleted!"
```

**Save this as `delete_all_workflows.ps1` and run:**
```powershell
.\delete_all_workflows.ps1
```

---

## Method 3: Direct Database Commands

### ✅ Best for: Advanced users, specific table cleanup

**Step 1: Open SQLite database**
```cmd
cd D:\Downloads\UMHack\backend
sqlite3 stitchflow.db
```

**Step 2: Run SQL commands**

### View all tables:
```sql
.tables
```

### View workflow count:
```sql
SELECT COUNT(*) FROM workflows;
```

### View all workflows:
```sql
SELECT workflow_id, state, created_by, created_at FROM workflows;
```

### Delete all workflows:
```sql
DELETE FROM decisions;
DELETE FROM policy_screening_results;
DELETE FROM reasoning_results;
DELETE FROM audit_log;
DELETE FROM workflows;
```

### Delete workflows by state:
```sql
-- Delete only "New" workflows
DELETE FROM workflows WHERE state = 'New';

-- Delete only "Failed" workflows
DELETE FROM workflows WHERE state = 'Failed';
```

### Delete workflows by date:
```sql
-- Delete workflows older than a specific date
DELETE FROM workflows WHERE created_at < '2024-04-23';
```

### Delete workflows by creator:
```sql
-- Delete workflows created by specific user
DELETE FROM workflows WHERE created_by = 'test@example.com';
```

### Exit SQLite:
```sql
.exit
```

---

## Method 4: Delete Database File

### ✅ Best for: Complete fresh start, nuclear option

**⚠️ WARNING: This deletes EVERYTHING including policy rules!**

**Step 1: Stop the backend server**
- Go to terminal where backend is running
- Press `CTRL+C`

**Step 2: Delete the database file**
```cmd
cd D:\Downloads\UMHack\backend
del stitchflow.db
```

**Step 3: Recreate the database**
```cmd
python setup_database.py
```
- Type `y` when asked to seed policy rules

**Step 4: Restart backend**
```cmd
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Method 5: Delete Uploaded Files

### ✅ Best for: Freeing up disk space

Uploaded documents are stored in `backend/uploads/` folder.

### View uploaded files:
```cmd
cd D:\Downloads\UMHack\backend\uploads
dir
```

### Delete all uploaded files:
```cmd
cd D:\Downloads\UMHack\backend\uploads
del *.*
```

### Delete specific file:
```cmd
cd D:\Downloads\UMHack\backend\uploads
del {workflow_id}_{filename}
```

**Example:**
```cmd
del 9c8b2780-4b81-446c-9d29-44335a5e1f20_test_event.txt
```

---

## Complete Reset (Everything)

### 🔥 Nuclear Option: Delete Everything and Start Fresh

**This will:**
- Delete all workflows
- Delete all uploaded files
- Delete all database data
- Reset to factory state

**Step 1: Stop backend server**
- Press `CTRL+C` in backend terminal

**Step 2: Delete database**
```cmd
cd D:\Downloads\UMHack\backend
del stitchflow.db
```

**Step 3: Delete uploaded files**
```cmd
cd D:\Downloads\UMHack\backend\uploads
del *.*
```

**Step 4: Recreate database**
```cmd
cd D:\Downloads\UMHack\backend
venv\Scripts\activate.bat
python setup_database.py
```
- Type `y` to seed policy rules

**Step 5: Restart backend**
```cmd
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Step 6: Refresh frontend**
- Go to browser
- Press `F5` to refresh
- You should see 0 workflows

---

## 📊 Verification Commands

### Check if data was deleted:

**Method 1: Using the script**
```cmd
python clear_database.py
# Choose option 1 (View statistics)
```

**Method 2: Using API**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/workflows"
```

**Method 3: Using SQLite**
```cmd
sqlite3 stitchflow.db "SELECT COUNT(*) FROM workflows;"
```

**Method 4: Check frontend**
- Open http://localhost:5174
- Dashboard should show 0 workflows

---

## 🎯 Recommended Workflow

### For Regular Cleanup (Keep Audit Trail):
```cmd
cd D:\Downloads\UMHack\backend
venv\Scripts\activate.bat
python clear_database.py
# Choose option 2
```

### For Complete Fresh Start:
```cmd
cd D:\Downloads\UMHack\backend
venv\Scripts\activate.bat
python clear_database.py
# Choose option 3
```

### For Testing (Quick Reset):
```cmd
# Stop backend (CTRL+C)
cd D:\Downloads\UMHack\backend
del stitchflow.db
python setup_database.py
# Type 'y'
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔍 Troubleshooting

### Problem: "Database is locked"
**Solution:** Stop the backend server first
```cmd
# Press CTRL+C in backend terminal
# Then run your delete command
```

### Problem: "Permission denied"
**Solution:** Make sure no programs are using the database
```cmd
# Close any SQLite browser tools
# Stop the backend server
# Then try again
```

### Problem: "File not found"
**Solution:** Make sure you're in the correct directory
```cmd
cd D:\Downloads\UMHack\backend
# Then run your command
```

### Problem: Frontend still shows old data
**Solution:** Refresh the browser
```
Press F5 in browser
Or CTRL+SHIFT+R for hard refresh
```

---

## 📝 Summary Table

| Method | Speed | Safety | Keeps Audit Log | Keeps Policy Rules |
|--------|-------|--------|-----------------|-------------------|
| Script Option 2 | Fast | ✅ Safe | ✅ Yes | ✅ Yes |
| Script Option 3 | Fast | ⚠️ Caution | ❌ No | ✅ Yes |
| API Delete | Medium | ✅ Safe | ✅ Yes | ✅ Yes |
| SQL Commands | Fast | ⚠️ Advanced | Depends | Depends |
| Delete DB File | Instant | 🔥 Nuclear | ❌ No | ❌ No |

---

## 🎓 Best Practices

1. **Always view statistics first** (Option 1) before deleting
2. **Keep audit logs** unless you need a complete reset
3. **Backup database** before major deletions:
   ```cmd
   copy stitchflow.db stitchflow_backup.db
   ```
4. **Stop backend server** before deleting database file
5. **Test with small deletions** before bulk operations

---

**Need help? Check the main README.md or START_HERE.md**
