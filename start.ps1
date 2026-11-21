# SRK Placement AI - laptop par chalane ke liye (Windows + Docker Desktop)
# Double-click start.bat, ya PowerShell mein:  .\start.ps1
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker Desktop nahi mila. Pehle install karein: https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
  Read-Host "Enter dabayein"; exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Docker Desktop chalu nahi hai. Use kholiye, 1-2 minute rukiye, phir dobara chalaiye." -ForegroundColor Red
  Read-Host "Enter dabayein"; exit 1
}

function RandHex($n) { -join ((1..$n) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }) }

if (-not (Test-Path .env)) {
  (Get-Content .env.example) `
    -replace '^JWT_SECRET=.*', "JWT_SECRET=$(RandHex 32)" `
    -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(RandHex 16)" `
    -replace '^APP_PORT=.*', 'APP_PORT=8080' |
    Set-Content .env -Encoding ascii
  Write-Host ".env bana di (demo data ke saath)."
}

Write-Host "App ban raha hai... pehli baar 5-10 minute lagte hain." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Read-Host "Kuch galat hua. Upar ka error dekhein. Enter dabayein"; exit 1 }

Write-Host "App start ho raha hai..."
for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-WebRequest -UseBasicParsing http://localhost:8080/api/health -TimeoutSec 3 | Out-Null; break } catch { Start-Sleep 3 }
}
Start-Process "http://localhost:8080"
Write-Host ""
Write-Host "Chal gaya!  http://localhost:8080" -ForegroundColor Green
Write-Host "Demo login (password Srk@2026): tpo@srk.demo, coord.esm@srk.demo, student001@srk.demo"
Write-Host "Band karne ke liye:  docker compose stop"
Read-Host "Enter dabayein"
