$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$buildEnv = Join-Path $env:TEMP 'CircuitStudioAI-build-venv'
$buildPython = Join-Path $buildEnv 'Scripts\python.exe'
$buildWork = Join-Path $env:TEMP 'CircuitStudioAI-pyinstaller-work'
$dist = Join-Path $PSScriptRoot 'dist\CircuitStudioAI'

if (Test-Path -LiteralPath $dist) {
    throw "既存配布フォルダーを保持するためビルドを停止しました: $dist"
}
if (-not (Test-Path -LiteralPath $buildPython)) {
    & py -3.11 -m venv $buildEnv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11のビルド環境を作成できません。' }
}
& $buildPython -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'PyInstallerをインストールできません。' }
& $buildPython -m PyInstaller --clean --noconfirm --workpath $buildWork (Join-Path $PSScriptRoot 'CircuitStudioAI.spec')
if ($LASTEXITCODE -ne 0) { throw 'PyInstallerのビルドに失敗しました。' }

Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination (Join-Path $dist 'README.md')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.md') -Destination (Join-Path $dist 'THIRD_PARTY_NOTICES.md')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'docs\ユーザーマニュアル.md') -Destination (Join-Path $dist 'ユーザーマニュアル.md')

foreach ($doc in @('INSTALL.md', 'CONTRIBUTING.md', 'CHANGELOG.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $doc) -Destination (Join-Path $dist $doc)
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'docs') -Destination (Join-Path $dist 'docs') -Recurse
$samplesSource = Join-Path $PSScriptRoot 'samples'
$samplesDestination = Join-Path $dist 'samples'
$sampleFiles = Get-ChildItem -LiteralPath $samplesSource -File -Recurse | Where-Object {
    $_.Name -notlike '*-netlist.xml' -and
    $_.Name -ne 'netlist.xml' -and
    $_.Name -notin @('diagnostics.json', 'pcb_diagnostics.json', 'spice_results.json') -and
    $_.Extension -notin @('.kicad_prl', '.lck', '.log') -and
    $_.FullName -notmatch '[\\/]backups[\\/]'
}
foreach ($sample in $sampleFiles) {
    $relative = $sample.FullName.Substring($samplesSource.Length).TrimStart([char[]]@([char]92, [char]47))
    $target = Join-Path $samplesDestination $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $sample.FullName -Destination $target
}
$reportsDir = Join-Path $dist 'reports'
New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
foreach ($report in @('test-results.md', 'kicad10-environment-audit.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('reports\' + $report)) -Destination (Join-Path $reportsDir $report)
}

$ngspiceSource = Join-Path $PSScriptRoot 'tools\ngspice-47'
if (Test-Path -LiteralPath $ngspiceSource) {
    $toolsDir = Join-Path $dist 'tools'
    New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
    Copy-Item -LiteralPath $ngspiceSource -Destination $toolsDir -Recurse
}

$pythonRoot = (& py -3.11 -c 'import sys; print(sys.prefix)').Trim()
$licenses = Join-Path $dist 'THIRD_PARTY_LICENSES'
New-Item -ItemType Directory -Path $licenses -Force | Out-Null
$pythonLicense = Join-Path $pythonRoot 'LICENSE.txt'
$tkLicense = Join-Path $pythonRoot 'tcl\tk8.6\license.terms'
if (Test-Path -LiteralPath $pythonLicense) {
    Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $licenses 'Python-LICENSE.txt')
}
if (Test-Path -LiteralPath $tkLicense) {
    Copy-Item -LiteralPath $tkLicense -Destination (Join-Path $licenses 'Tcl-Tk-license.terms')
}
Write-Output "Build complete: $(Join-Path $dist 'CircuitStudioAI.exe')"
