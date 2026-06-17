param(
    [int]$Users = 20,
    [int]$SpawnRate = 2,
    [string]$RunTime = "5m",
    [string]$ResultsDir = ".\load_tests\results",
    [string]$Prefix = "submit_request"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$resultsPath = Join-Path $ResultsDir "${Prefix}_${timestamp}"

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null

Write-Host "Locust CSV prefix: $resultsPath"
Write-Host "Users=$Users SpawnRate=$SpawnRate RunTime=$RunTime"

locust `
  -f .\load_tests\locustfile.py `
  --headless `
  -u $Users `
  -r $SpawnRate `
  -t $RunTime `
  --csv "$resultsPath"
