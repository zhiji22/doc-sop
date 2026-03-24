cd $PSScriptRoot
# 内容：用当前目录的 .venv 的 python 执行传入参数
& "$PSScriptRoot\.venv\Scripts\Activate.ps1" @args
$env:PYTHONPATH = "."
arq app.worker.WorkerSettings