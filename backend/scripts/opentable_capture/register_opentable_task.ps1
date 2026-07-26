<#
.SYNOPSIS
  OpenTable ローカル自動キャプチャを Windows タスクスケジューラに日次登録する。

.DESCRIPTION
  run_opentable_capture.bat を毎日決まった時刻に実行するタスクを作成する。
  PC が起動していなかった場合は次回起動時にキャッチアップ実行する
  (StartWhenAvailable)。

.PARAMETER At
  実行時刻 (HH:mm, ローカル時刻)。既定 09:00。
  OpenTable は米国時間 10:00 ET 頃に更新されるため (=JST 深夜)、
  翌朝 09:00 に走らせれば前日ぶんの最新データを取得できる。

.PARAMETER TaskName
  タスク名。既定 "EconAlpha OpenTable Capture"。

.EXAMPLE
  # 既定 (毎日 09:00) で登録
  powershell -ExecutionPolicy Bypass -File .\register_opentable_task.ps1

.EXAMPLE
  # 毎日 12:30 に変更して登録
  powershell -ExecutionPolicy Bypass -File .\register_opentable_task.ps1 -At 12:30

.NOTES
  - 事前に run_opentable_capture.example.bat を run_opentable_capture.bat にコピーし、
    master パスワードを設定しておくこと。
  - 既定では「ユーザーがログオンしているときのみ実行」。ログオフ中も走らせたい場合は
    タスクスケジューラで「ユーザーがログオンしているかどうかにかかわらず実行」に変更する。
  - 解除: Unregister-ScheduledTask -TaskName "EconAlpha OpenTable Capture" -Confirm:$false
#>
param(
    [string]$At = "09:00",
    [string]$TaskName = "EconAlpha OpenTable Capture"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$bat = Join-Path $scriptDir "run_opentable_capture.bat"

if (-not (Test-Path $bat)) {
    Write-Error "run_opentable_capture.bat が見つかりません。`n" +
        "run_opentable_capture.example.bat をコピーして master パスワードを設定してください:`n  $bat"
    exit 1
}

# 実行時刻をパース
try {
    $trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::ParseExact($At, "HH:mm", $null))
} catch {
    Write-Error "実行時刻の形式が不正です (HH:mm で指定): '$At'"
    exit 1
}

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`"" -WorkingDirectory $scriptDir

# PC がオフだった時刻ぶんは次回起動時にキャッチアップ実行
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "OpenTable 予約件数スクショを実Chromeで撮影し /api/usa/opentable/upload へ投稿 (Akamai回避のローカル半自動)" `
    -Force | Out-Null

Write-Host "登録しました: タスク '$TaskName' を毎日 $At に実行します。" -ForegroundColor Green
Write-Host "今すぐ試すには: Start-ScheduledTask -TaskName `"$TaskName`"" -ForegroundColor Cyan
Write-Host "ログ: $(Join-Path $scriptDir 'opentable_capture.log')" -ForegroundColor Cyan
