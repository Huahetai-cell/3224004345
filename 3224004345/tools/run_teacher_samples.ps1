param(
    [Parameter(Mandatory = $true)]
    [string]$ZipPath,
    [string]$OutputDirectory = "$env:TEMP\teacher-paper-tests-3224004345"
)

$ErrorActionPreference = "Stop"
$projectDirectory = Split-Path -Parent $PSScriptRoot
$mainPath = Join-Path $projectDirectory "main.py"

if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
    throw "找不到测试数据压缩包：$ZipPath"
}

if (Test-Path -LiteralPath $OutputDirectory) {
    Remove-Item -LiteralPath $OutputDirectory -Recurse -Force
}
Expand-Archive -LiteralPath $ZipPath -DestinationPath $OutputDirectory -Force

$originalPath = Join-Path $OutputDirectory "orig.txt"
if (-not (Test-Path -LiteralPath $originalPath -PathType Leaf)) {
    throw "压缩包中缺少 orig.txt：$ZipPath"
}

Get-ChildItem -LiteralPath $OutputDirectory -Filter "orig_*.txt" -File |
    Where-Object { $_.BaseName -notmatch "_answer$" } |
    Sort-Object Name |
    ForEach-Object {
        $answerPath = Join-Path $OutputDirectory ($_.BaseName + "_answer.txt")
        & python $mainPath $originalPath $_.FullName $answerPath
        $exitCode = $LASTEXITCODE
        $answer = if (Test-Path -LiteralPath $answerPath) {
            (Get-Content -LiteralPath $answerPath -Raw).Trim()
        } else {
            "<未生成>"
        }
        [PSCustomObject]@{
            Input = $_.Name
            ExitCode = $exitCode
            Answer = $answer
        }
    } | Format-Table -AutoSize

