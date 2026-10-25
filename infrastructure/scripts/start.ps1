$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item .env.example .env }
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose up --build -d
exit $LASTEXITCODE
