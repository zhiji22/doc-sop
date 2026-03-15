# 内容：用当前目录的 .venv 的 python 执行传入参数
& "$PSScriptRoot\.venv\Scripts\Activate.ps1" @args
# 使用 .venv 的 Python 启动 API 服务
& "$PSScriptRoot\run.ps1" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
