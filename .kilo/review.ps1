[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$kiloApplication = Get-Command kilo -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
$kiloExecutable = if ($null -ne $kiloApplication) {
    $kiloApplication.Source
} else {
    $extensionsRoot = Join-Path $env:USERPROFILE ".vscode\extensions"
    $bundledKilo = Get-ChildItem -LiteralPath $extensionsRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "kilocode.kilo-code-*" } |
        Sort-Object LastWriteTime -Descending |
        ForEach-Object { Join-Path $_.FullName "bin\kilo.exe" } |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
    $bundledKilo
}

if ([string]::IsNullOrWhiteSpace($kiloExecutable) -or
    -not (Test-Path -LiteralPath $kiloExecutable)) {
    [Console]::Error.WriteLine(
        "Kilo CLI was not found on PATH or in the installed VS Code Kilo extension."
    )
    exit 127
}

$reviewPrompt = @"
Perform an independent final review of the current uncommitted implementation.
Follow repository instructions and retrieve only relevant architecture,
research, decision, and evidence context. Return only substantive findings.
"@

try {
    & $kiloExecutable run --dir $repositoryRoot --title "Codex Kilo Contract Review" --agent ask --model openrouter/z-ai/glm-5.3 --variant max --command codex-contract-review $reviewPrompt.Trim()
} catch {
    [Console]::Error.WriteLine(
        "Kilo contract-reviewer invocation failed: $($_.Exception.Message)"
    )
    exit 1
}

$invocationExitCode = $LASTEXITCODE
if ($invocationExitCode -ne 0) {
    [Console]::Error.WriteLine("Kilo contract-reviewer exited with code $invocationExitCode.")
    exit $invocationExitCode
}
