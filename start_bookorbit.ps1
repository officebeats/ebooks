$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$bookorbitDir = Join-Path $scriptDir "bookorbit"
$envFile = Join-Path $bookorbitDir ".env"

Write-Host "Scaffolding .env file for BookOrbit..."
$appUrl = "http://localhost:3000"
$booksPath = "C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks\Epubs"

# Helper function to generate hex strings
function Get-RandomHex($Length) {
    $bytes = New-Object byte[] ($Length / 2)
    (New-Object Random).NextBytes($bytes)
    return -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

$pgPass = Get-RandomHex -Length 24
$jwtSecret = Get-RandomHex -Length 32
$setupToken = "591ec2aee7941d7d" # keeping the one already generated so the user doesn't get confused

$envContent = @"
APP_IMAGE=ghcr.io/bookorbit/bookorbit:latest
APP_PORT=3000
APP_URL=$appUrl
BOOKS_HOST_PATH=$booksPath

POSTGRES_USER=bookorbit
POSTGRES_PASSWORD=$pgPass
POSTGRES_DB=bookorbit

JWT_SECRET=$jwtSecret
SETUP_BOOTSTRAP_TOKEN=$setupToken

PUID=1000
PGID=1000

# Optional: start library folder picker at /books
LIBRARY_BROWSE_ROOT=/books
"@
Set-Content -Path $envFile -Value $envContent
Write-Host ".env created with secure random tokens."
Write-Host "========================================================="
Write-Host "IMPORTANT: Your setup bootstrap token is: $setupToken"
Write-Host "========================================================="

Write-Host "Checking if Docker is running..."
try {
    docker info > $null 2>&1
} catch {
    Write-Error "Docker is not running or not installed. Please start Docker Desktop first."
    exit 1
}

Write-Host "Starting BookOrbit via docker compose..."
Set-Location -Path $bookorbitDir
docker compose up -d
Write-Host "BookOrbit should now be starting up. It will be available at http://localhost:3000"
Write-Host "Use your setup bootstrap token to configure it on the first run."
