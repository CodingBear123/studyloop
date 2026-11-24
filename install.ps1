# Claude Study Tool installer for Windows. Safe to run again: it updates what is there.
#
#   From a downloaded copy: right-click install.ps1 > Run with PowerShell
#   Straight from GitHub:   irm https://raw.githubusercontent.com/CodingBear123/claude-study-tool/main/install.ps1 | iex
#
# What it does: checks Python (installs it with winget if missing), gets the tool (into
# %USERPROFILE%\.claude-study-tool unless run from a copy), copies the /study and /study-vault skills into
# %USERPROFILE%\.claude\skills, adds a "Claude Study" shortcut to the Desktop and Start menu, and checks for Claude Code.
$ErrorActionPreference = "Stop"
$Repo = "CodingBear123/claude-study-tool"
$Dest = if ($env:CLAUDE_STUDY_HOME) { $env:CLAUDE_STUDY_HOME } else { Join-Path $HOME ".claude-study-tool" }
$Skills = Join-Path $HOME ".claude\skills"

function Bold($t) { Write-Host ""; Write-Host $t -ForegroundColor White }
function Ok($t) { Write-Host "  + $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  ! $t" -ForegroundColor Yellow }
function Ask($q) { $a = Read-Host "  $q [Y/n]"; return -not ($a -match '^[nN]') }
function Done($code) { if ($code) { Read-Host "Press Enter to close" | Out-Null }; exit $code }

function Find-Python {
  foreach ($c in @(@("py", "-3"), @("python"), @("python3"))) {
    try {
      $rest = @($c | Select-Object -Skip 1)
      $exe = & $c[0] @rest -c "import sys; print(sys.executable) if sys.version_info >= (3, 9) else sys.exit(1)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) { return $exe.Trim() }
    } catch {}
  }
  return $null
}

Bold "Claude Study Tool"

Bold "1/4 Python"
$Py = Find-Python
if (-not $Py) {
  if ((Get-Command winget -ErrorAction SilentlyContinue) -and (Ask "Python isn't installed. Install it now?")) {
    winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
    $Py = Find-Python
  }
  if (-not $Py) { Warn "Install Python 3 from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this again."; Done 1 }
}
$Pyw = Join-Path (Split-Path $Py) "pythonw.exe"
if (-not (Test-Path $Pyw)) { $Pyw = $Py }
Ok "Python: $Py"

Bold "2/4 Claude Study Tool"
$Here = if ($PSScriptRoot) { $PSScriptRoot } else { "" }
if ($Here -and (Test-Path (Join-Path $Here "skills\study\app\server.py"))) {
  $Src = $Here; Ok "using this copy: $Src"
} else {
  $zip = Join-Path $env:TEMP "claude-study-tool.zip"
  $tmp = Join-Path $env:TEMP "claude-study-tool-unpacked"
  try {
    Invoke-WebRequest "https://codeload.github.com/$Repo/zip/refs/heads/main" -OutFile $zip -UseBasicParsing
  } catch {
    Warn "Couldn't download $Repo. If the repository is private, download it as a ZIP from GitHub,"
    Warn "unpack it, and run install.ps1 from inside that folder."
    Done 1
  }
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
  Expand-Archive $zip $tmp -Force
  if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
  Move-Item (Get-ChildItem $tmp | Select-Object -First 1).FullName $Dest
  Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
  $Src = $Dest; Ok "downloaded to $Dest"
}
$App = Join-Path $Src "skills\study\app"

Bold "3/4 /study and /study-vault for Claude"
New-Item -ItemType Directory -Force $Skills | Out-Null
foreach ($s in @("study", "study-vault")) {
  $t = Join-Path $Skills $s
  if (Test-Path $t) { Remove-Item $t -Recurse -Force }
  Copy-Item (Join-Path $Src "skills\$s") $t -Recurse   # a copy: links need admin rights on Windows; run this again to update
  Ok "/$s"
}

Bold "4/4 The Claude Study shortcut"
$shell = New-Object -ComObject WScript.Shell
$places = @([Environment]::GetFolderPath("Desktop"), (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"))
foreach ($dir in $places) {
  $lnk = $shell.CreateShortcut((Join-Path $dir "Claude Study.lnk"))
  $lnk.TargetPath = $Pyw
  $lnk.Arguments = "`"$(Join-Path $App 'launch.py')`""
  $lnk.WorkingDirectory = $App
  $lnk.Description = "Open the study page"
  $lnk.Save()
}
Ok "Desktop and Start menu: Claude Study"

if (Get-Command claude -ErrorAction SilentlyContinue) { Ok "Claude Code" }
else {
  Warn "Claude Code isn't installed. /study and /study-vault run inside it, and the page uses it for"
  Warn "'Check with Claude' and 'Ask Claude'."
  if (Ask "Install Claude Code now (official installer from claude.ai)?") {
    Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    Ok "Claude Code installed; run 'claude' once to sign in"
  } else { Warn "Later: https://claude.com/claude-code" }
}

Bold "Done."
Write-Host "  Make study notes: open Claude in your course folder and type /study-vault"
Write-Host "  Study:            type /study, or double-click Claude Study on your Desktop"
Read-Host "Press Enter to close" | Out-Null
