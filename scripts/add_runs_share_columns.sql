-- 为 public.runs 添加分享相关列与索引
alter table public.runs
add column if not exists share_id text unique,
add column if not exists is_public boolean not null default false;
create index if not exists idx_runs_share_id on public.runs(share_id);
