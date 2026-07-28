'==========================================================================
' Lagrange Agent Server - Cleanup Script
' Cleans old logs, temporary files, expired database records, and cache.
' Uses WScript.Shell and FileSystemObject for Windows-based maintenance.
'==========================================================================

Option Explicit

' --- Constants ---
Const LOG_DIR           = "logs"
Const TEMP_DIR          = "temp"
Const CACHE_DIR         = "cache"
Const DB_PATH           = "data\lagrange.db"
Const MAX_LOG_AGE_DAYS  = 30
Const MAX_TEMP_AGE_DAYS = 7
Const MAX_BATTLE_AGE_DAYS = 90
Const DRY_RUN           = False   ' Set True for testing without actual deletes

Dim objFSO, objShell, objLogFile
Dim deletedCount, errorCount, freedBytes

' --- Initialize ---
Set objFSO   = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")

deletedCount = 0
errorCount   = 0
freedBytes   = 0

' --- Main ---
WScript.Echo "============================================"
WScript.Echo " Lagrange Cleanup Script - " & Now()
WScript.Echo " Dry Run: " & DRY_RUN
WScript.Echo "============================================"

CleanOldFiles LOG_DIR, MAX_LOG_AGE_DAYS, "*.log"
CleanOldFiles TEMP_DIR, MAX_TEMP_AGE_DAYS, "*.*"
CleanOldFiles CACHE_DIR, MAX_TEMP_AGE_DAYS, "*.*"
CleanExpiredBattleRecords
RemoveEmptyDirs TEMP_DIR
RemoveEmptyDirs CACHE_DIR
ReportOrphanedFiles

WScript.Echo "--------------------------------------------"
WScript.Echo " Cleanup Summary:"
WScript.Echo "  Files deleted : " & deletedCount
WScript.Echo "  Errors        : " & errorCount
WScript.Echo "  Space freed   : " & FormatBytes(freedBytes)
WScript.Echo "============================================"

'==========================================================================
' CleanOldFiles - Delete files older than N days in a directory
'==========================================================================
Sub CleanOldFiles(dirPath, maxAgeDays, filePattern)
    Dim folder, file, cutoffDate

    If Not objFSO.FolderExists(dirPath) Then
        WScript.Echo "[SKIP] Directory not found: " & dirPath
        Exit Sub
    End If

    Set folder = objFSO.GetFolder(dirPath)
    cutoffDate = DateAdd("d", -maxAgeDays, Now())

    WScript.Echo "[CLEAN] Scanning " & dirPath & " for files older than " & maxAgeDays & " days..."

    For Each file In folder.Files
        If MatchesPattern(file.Name, filePattern) Then
            If file.DateLastModified < cutoffDate Then
                Dim sizeBytes : sizeBytes = file.Size
                If DRY_RUN Then
                    WScript.Echo "  [DRY-RUN] Would delete: " & file.Path & " (" & FormatBytes(sizeBytes) & ")"
                Else
                    On Error Resume Next
                    objFSO.DeleteFile file.Path, True
                    If Err.Number = 0 Then
                        WScript.Echo "  [DELETED] " & file.Path & " (" & FormatBytes(sizeBytes) & ")"
                        deletedCount = deletedCount + 1
                        freedBytes = freedBytes + sizeBytes
                    Else
                        WScript.Echo "  [ERROR] Cannot delete " & file.Path & ": " & Err.Description
                        errorCount = errorCount + 1
                        Err.Clear
                    End If
                    On Error Goto 0
                End If
            End If
        End If
    Next
End Sub

'==========================================================================
' CleanExpiredBattleRecords - Remove old battle results from database
'==========================================================================
Sub CleanExpiredBattleRecords()
    Dim cutoffStr, sql, dbPath

    dbPath = objFSO.BuildPath(objShell.CurrentDirectory, DB_PATH)
    If Not objFSO.FileExists(dbPath) Then
        WScript.Echo "[SKIP] Database not found: " & dbPath
        Exit Sub
    End If

    cutoffStr = Year(DateAdd("d", -MAX_BATTLE_AGE_DAYS, Now())) & "-" & _
                Right("0" & Month(DateAdd("d", -MAX_BATTLE_AGE_DAYS, Now())), 2) & "-" & _
                Right("0" & Day(DateAdd("d", -MAX_BATTLE_AGE_DAYS, Now())), 2)

    WScript.Echo "[DB] Purging battle records older than " & cutoffStr & "..."

    sql = "sqlite3 """ & dbPath & """ ""DELETE FROM battle_results WHERE battle_date < '" & cutoffStr & "';"" "
    If Not DRY_RUN Then
        objShell.Run "cmd /c " & sql, 0, True
        sql = "sqlite3 """ & dbPath & """ ""DELETE FROM fleet_logs WHERE timestamp < '" & cutoffStr & "';"" "
        objShell.Run "cmd /c " & sql, 0, True
        sql = "sqlite3 """ & dbPath & """ ""VACUUM;"" "
        objShell.Run "cmd /c " & sql, 0, True
        WScript.Echo "[DB] Old battle records purged and database vacuumed."
    Else
        WScript.Echo "[DB] DRY-RUN: Would purge records older than " & cutoffStr
    End If
End Sub

'==========================================================================
' RemoveEmptyDirs - Clean up empty subdirectories
'==========================================================================
Sub RemoveEmptyDirs(parentPath)
    Dim folder, subfolder

    If Not objFSO.FolderExists(parentPath) Then Exit Sub

    Set folder = objFSO.GetFolder(parentPath)
    For Each subfolder In folder.SubFolders
        If subfolder.Files.Count = 0 And subfolder.SubFolders.Count = 0 Then
            If Not DRY_RUN Then
                On Error Resume Next
                objFSO.DeleteFolder subfolder.Path, True
                If Err.Number = 0 Then
                    WScript.Echo "[CLEAN] Removed empty folder: " & subfolder.Path
                End If
                On Error Goto 0
            Else
                WScript.Echo "[DRY-RUN] Would remove: " & subfolder.Path
            End If
        End If
    Next
End Sub

'==========================================================================
' ReportOrphanedFiles - Find files not referenced by the application
'==========================================================================
Sub ReportOrphanedFiles()
    Dim tempFolder, file, orphanCount
    orphanCount = 0

    If Not objFSO.FolderExists(TEMP_DIR) Then Exit Sub

    Set tempFolder = objFSO.GetFolder(TEMP_DIR)
    For Each file In tempFolder.Files
        If Left(file.Name, 8) = "orphan_" Then
            orphanCount = orphanCount + 1
        End If
    Next

    If orphanCount > 0 Then
        WScript.Echo "[INFO] Found " & orphanCount & " orphaned temporary files in " & TEMP_DIR
    End If
End Sub

'==========================================================================
' MatchesPattern - Simple wildcard pattern matching
'==========================================================================
Function MatchesPattern(fileName, pattern)
    If pattern = "*.*" Or pattern = "*" Then
        MatchesPattern = True
    ElseIf Left(pattern, 2) = "*." Then
        Dim ext : ext = LCase(Mid(pattern, 2))
        MatchesPattern = (LCase(objFSO.GetExtensionName(fileName)) = LCase(Mid(pattern, 3)))
    Else
        MatchesPattern = (LCase(fileName) = LCase(pattern))
    End If
End Function

'==========================================================================
' FormatBytes - Human-readable byte formatting
'==========================================================================
Function FormatBytes(bytes)
    If bytes >= 1073741824 Then
        FormatBytes = FormatNumber(bytes / 1073741824, 2) & " GB"
    ElseIf bytes >= 1048576 Then
        FormatBytes = FormatNumber(bytes / 1048576, 2) & " MB"
    ElseIf bytes >= 1024 Then
        FormatBytes = FormatNumber(bytes / 1024, 2) & " KB"
    Else
        FormatBytes = bytes & " B"
    End If
End Function

' --- Cleanup ---
Set objFSO   = Nothing
Set objShell = Nothing
