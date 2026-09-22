$ErrorActionPreference = 'Stop'

uv run ruff check .
uv run pytest
Push-Location web
try {
    npm ci
    npm audit --audit-level=high
    npm run build
}
finally {
    Pop-Location
}
