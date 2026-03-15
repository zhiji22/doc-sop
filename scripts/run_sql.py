#!/usr/bin/env python3
"""
用项目中的 DATABASE_URL 执行 SQL 文件。
用法（在项目根目录）:
  使用 API 虚拟环境（推荐，避免缺依赖）:
    apps\api\.venv\Scripts\python scripts/run_sql.py scripts/add_runs_share_columns.sql
  或直接:
    python scripts/run_sql.py scripts/add_runs_share_columns.sql
"""
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip("'\"").strip()
        if k:
            os.environ[k] = v


# 加载 .env：先项目根目录，再 apps/api（后者可覆盖）
_load_env(repo_root / ".env")
_load_env(repo_root / "apps" / "api" / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("错误: 未设置 DATABASE_URL。请在项目根目录或 apps/api 下配置 .env。", file=sys.stderr)
    sys.exit(1)

from sqlalchemy import create_engine, text


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/run_sql.py <sql文件路径>", file=sys.stderr)
        sys.exit(1)
    sql_path = Path(sys.argv[1])
    if not sql_path.is_absolute():
        sql_path = (repo_root / sql_path).resolve()
    if not sql_path.exists():
        print(f"文件不存在: {sql_path}", file=sys.stderr)
        sys.exit(1)
    sql = sql_path.read_text(encoding="utf-8").strip()
    if not sql:
        print("SQL 文件为空，跳过。")
        return

    def strip_leading_comments(stmt: str) -> str:
        lines = []
        for line in stmt.splitlines():
            l = line.strip()
            if l and not l.startswith("--"):
                lines.append(line)
            elif l.startswith("--") and not lines:
                continue  # 跳过仅出现在语句前的注释行
            elif lines:
                lines.append(line)
        return "\n".join(lines).strip() if lines else ""

    # 按分号拆成多条语句执行；去掉每条前面的注释，避免整条被误判为“仅注释”而跳过
    statements = []
    for s in sql.split(";"):
        stmt = strip_leading_comments(s.strip())
        if stmt:
            statements.append(stmt)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt + ";"))
    print("SQL 执行完成。")


if __name__ == "__main__":
    main()
