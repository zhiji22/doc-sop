# 从 .env 读取 DATABASE_URL 并启动 psql 交互式命令行（类似 mysql -u root -p 进到里面输 SQL）
# 用法：在项目根目录执行 .\scripts\psql.ps1

$ErrorActionPreference = "Stop"
$repoRoot = (Get-Item $PSScriptRoot).Parent.FullName

$envFiles = @(
    Join-Path $repoRoot ".env",
    Join-Path $repoRoot "apps" "api" ".env"
)
foreach ($f in $envFiles) {
    if (Test-Path $f) {
        Get-Content $f | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                $key = $matches[1].Trim()
                $val = $matches[2].Trim().Trim('"').Trim("'")
                [Environment]::SetEnvironmentVariable($key, $val, "Process")
            }
        }
    }
}

$url = [Environment]::GetEnvironmentVariable("DATABASE_URL", "Process")
if (-not $url) {
    Write-Host "错误: 未设置 DATABASE_URL。请在 .env 或 apps/api/.env 中配置。" -ForegroundColor Red
    exit 1
}
# psql 只认 postgresql://，不认 postgresql+psycopg://
$url = $url -replace '\+psycopg2?', ''

$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    Write-Host "未找到 psql。请安装 PostgreSQL 客户端（或完整安装 PostgreSQL）并确保 psql 在 PATH 中。" -ForegroundColor Red
    exit 1
}

& psql "$url"
