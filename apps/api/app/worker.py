"""
ARQ Worker 配置
这个文件定义了后台任务工人的所有配置和任务函数。
启动方式：arq app.worker.WorkerSettings
"""
from arq.connections import RedisSettings
from app.core.config import settings
from app.services.run_service import process_run


async def task_process_run(ctx: dict, run_id: str, user_id: str):
  """
  ARQ 任务函数：处理一个生成任务。
  
  ARQ 要求任务函数的第一个参数是 ctx（上下文字典），
  后面业务参数。
  
  这个函数只是一个"壳"，实际逻辑还是调你已有的 process_run。
  """
  # process_run 是同步函数，直接调用就行
  # ARQ 虽然是异步框架，但支持调用同步函数
  process_run(run_id=run_id, user_id=user_id)


def parse_redis_url(url: str) -> RedisSettings:
  """
  把 redis://host:port 格式的 URL 解析成 ARQ 需要的 RedisSettings。
  """
  # 去掉 redis:// 前缀
  url = url.replace("redis://", "")

  # 分离host，port
  if ":" in url:
    host, port_str = url.split(":", 1)
    # host后面可能还有 /db_number,去掉
    port = int(port_str.split("/")[0])
  else:
    host = url.split("/")[0]
    port = 6379

  return RedisSettings(host=host, port=port)


class WorkerSettings:
  """
  ARQ Worker 的配置类。
  ARQ 会自动读取这个类的属性来配置 worker。
  """
  # 注册所有任务函数
  functions = [task_process_run]
  
  # Redis 连接配置
  redis_settings = parse_redis_url(settings.REDIS_URL)
  
  # 任务超时时间（秒）—— LLM 调用可能比较慢，给 5 分钟
  job_timeout = 300
  
  # 最大同时执行的任务数 —— 控制并发，防止打爆 LLM API
  max_jobs = 3
  
  # 任务失败后的重试次数
  max_tries = 2
  
  # 健康检查间隔（秒）
  health_check_interval = 30

