# Studyloop installer for Windows. Safe to run again: it updates what is there.
#
#   From a downloaded copy: right-click install.ps1 > Run with PowerShell
#   Straight from GitHub:   irm https://raw.githubusercontent.com/CodingBear123/studyloop/main/install.ps1 | iex
#
# What it does: checks Python (installs it with winget if missing), gets the tool with git or as a ZIP (into
# %USERPROFILE%\.studyloop unless run from a copy), copies the /studyloop and /studyloop-setup skills into
# %USERPROFILE%\.claude\skills, adds a "Studyloop" shortcut to the Desktop and Start menu, and checks for Claude Code.
$ErrorActionPreference = "Stop"
$Repo = "CodingBear123/studyloop"
$Dest = if ($env:STUDYLOOP_HOME) { $env:STUDYLOOP_HOME } else { Join-Path $HOME ".studyloop" }
$Skills = Join-Path $HOME ".claude\skills"

function Bold($t) { Write-Host ""; Write-Host $t -ForegroundColor White }
function Ok($t) { Write-Host "  + $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  ! $t" -ForegroundColor Yellow }
function Ask($q) { $a = Read-Host "  $q [Y/n]"; return -not ($a -match '^[nN]') }
function Done($code) { if ($code) { Read-Host "Press Enter to close" | Out-Null }; exit $code }

function Git-Ok {  # run git; $true if it worked (its messages on stderr must not stop this script)
  $ErrorActionPreference = "Continue"
  try { & git @args 2>&1 | Out-Null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

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

Bold "Studyloop"

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

Bold "2/4 Studyloop"
$Here = if ($PSScriptRoot) { $PSScriptRoot } else { "" }
$Old = Join-Path $HOME ".claude-study-tool"   # where it lived before the rename to Studyloop
if (-not $env:STUDYLOOP_HOME -and (Test-Path $Old) -and -not (Test-Path $Dest)) { Move-Item $Old $Dest; Ok "moved $Old to $Dest" }
if ($Here -and (Test-Path (Join-Path $Here "skills\studyloop\app\server.py"))) {
  $Src = $Here; Ok "using this copy: $Src"
} elseif ((Test-Path (Join-Path $Dest ".git")) -and (Get-Command git -ErrorAction SilentlyContinue)) {
  if (Git-Ok -C $Dest pull --ff-only --quiet) { Ok "updated $Dest" } else { Warn "couldn't update $Dest, keeping the version there" }
  $Src = $Dest
} elseif ((Get-Command git -ErrorAction SilentlyContinue) -and (Git-Ok clone --quiet "https://github.com/$Repo.git" "$Dest.new")) {
  # a git checkout can update itself from the page (Update Studyloop button)
  if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
  Move-Item "$Dest.new" $Dest
  $Src = $Dest; Ok "downloaded to $Dest"
} else {
  if (Test-Path "$Dest.new") { Remove-Item "$Dest.new" -Recurse -Force }
  $zip = Join-Path $env:TEMP "studyloop.zip"
  $tmp = Join-Path $env:TEMP "studyloop-unpacked"
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
$App = Join-Path $Src "skills\studyloop\app"

Bold "3/4 /studyloop and /studyloop-setup for Claude"
New-Item -ItemType Directory -Force $Skills | Out-Null
foreach ($old in @("study", "study-vault")) {   # the names before /studyloop and /studyloop-setup
  $t = Join-Path $Skills $old
  if ((Test-Path (Join-Path $t ".studyloop")) -or (Test-Path (Join-Path $t ".claude-study-tool"))) { Remove-Item $t -Recurse -Force; Ok "removed the old /$old copy" }
}
foreach ($s in @("studyloop", "studyloop-setup")) {
  $t = Join-Path $Skills $s
  $mark = Join-Path $t ".studyloop"   # left by this installer: such a copy is ours to replace
  if (Test-Path $t) {
    if ((Test-Path $mark) -or (Test-Path (Join-Path $t ".claude-study-tool"))) { Remove-Item $t -Recurse -Force }
    else {
      $bak = "$t.backup-$(Get-Date -Format yyyyMMddHHmmss)"
      Move-Item $t $bak
      Warn "moved your old $s skill folder aside ($(Split-Path $bak -Leaf))"
    }
  }
  Copy-Item (Join-Path $Src "skills\$s") $t -Recurse   # a copy: links need admin rights on Windows; run this again to update
  Set-Content -Path $mark -Value "Installed by install.ps1; running it again replaces this folder."
  Ok "/$s"
}

Bold "4/4 The Studyloop shortcut"
$shell = New-Object -ComObject WScript.Shell
$places = @([Environment]::GetFolderPath("Desktop"), (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"))
foreach ($dir in $places) {
  Remove-Item (Join-Path $dir "Claude Study.lnk") -ErrorAction SilentlyContinue   # the name before the rename
  $lnk = $shell.CreateShortcut((Join-Path $dir "Studyloop.lnk"))
  $lnk.TargetPath = $Pyw
  $lnk.Arguments = "`"$(Join-Path $App 'launch.py')`""
  $lnk.WorkingDirectory = $App
  $lnk.Description = "Open the study page"
  $lnk.Save()
}
Ok "Desktop and Start menu: Studyloop"
if (Ask "Start Studyloop in the background when you log in (so it opens instantly)?") {
  & $Py (Join-Path $App "launch.py") --autostart on | Out-Null
  Ok "starts at login (turn off: run launch.py --autostart off)"
}

if (Get-Command claude -ErrorAction SilentlyContinue) { Ok "Claude Code" }
else {
  Warn "Claude Code isn't installed. /studyloop and /studyloop-setup run inside it, and the page uses it for"
  Warn "'Check with Claude' and 'Ask Claude'."
  if (Ask "Install Claude Code now (official installer from claude.ai)?") {
    Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    Ok "Claude Code installed; run 'claude' once to sign in"
  } else { Warn "Later: https://claude.com/claude-code" }
}

Bold "Done."
Write-Host "  Make study notes: open Claude in your course folder and type /studyloop-setup"
Write-Host "  Study:            type /studyloop, or double-click Studyloop on your Desktop"
Read-Host "Press Enter to close" | Out-Null
