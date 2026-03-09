-- -- doc-sop 本地 Postgres 表结构
-- CREATE TABLE IF NOT EXISTS public.users (
--     id    text PRIMARY KEY,
--     email text
-- );

-- CREATE TABLE IF NOT EXISTS public.files (
--     id          uuid PRIMARY KEY,
--     user_id     text NOT NULL,
--     filename    text NOT NULL,
--     storage_key text NOT NULL,
--     mime        text,
--     size        bigint,
--     status      text NOT NULL DEFAULT 'uploaded'
-- );

-- CREATE TABLE IF NOT EXISTS public.runs (
--     id           uuid PRIMARY KEY,
--     user_id      text NOT NULL,
--     file_id      uuid NOT NULL,
--     template     text NOT NULL,
--     status       text NOT NULL,
--     result_json  jsonb,
--     error        text,
--     usage_tokens integer,
--     cost_usd     numeric(12, 6)
-- );

-- -- doc-sop 本地 Postgres 表结构（与 API main.py 一致）
-- CREATE TABLE IF NOT EXISTS public.users (
--     id   text PRIMARY KEY,
--     email text
-- );

-- CREATE TABLE IF NOT EXISTS public.files (
--     id          uuid PRIMARY KEY,
--     user_id     text NOT NULL,
--     filename    text NOT NULL,
--     storage_key text NOT NULL,
--     mime        text,
--     size        bigint,
--     status      text NOT NULL DEFAULT 'uploaded'
-- );

-- CREATE TABLE IF NOT EXISTS public.runs (
--     id           uuid PRIMARY KEY,
--     user_id      text NOT NULL,
--     file_id      uuid NOT NULL,
--     template     text NOT NULL,
--     status       text NOT NULL,
--     result_json  jsonb,
--     error        text,
--     usage_tokens integer,
--     cost_usd     numeric(12, 6)
-- );



-- users: 对应 Clerk userId
create table if not exists public.users (
  id text primary key,
  email text,
  created_at timestamptz not null default now()
);

-- files: 上传的文件记录
create table if not exists public.files (
  id uuid primary key default gen_random_uuid(),
  user_id text not null references public.users(id) on delete cascade,
  filename text not null,
  storage_key text not null,
  mime text,
  size bigint,
  status text not null default 'uploaded', -- uploaded|processing|ready|failed
  created_at timestamptz not null default now()
);

create index if not exists idx_files_user_id on public.files(user_id);

-- runs: 每次生成任务
create table if not exists public.runs (
  id uuid primary key default gen_random_uuid(),
  user_id text not null references public.users(id) on delete cascade,
  file_id uuid not null references public.files(id) on delete cascade,
  template text not null, -- sop|checklist|summary
  status text not null default 'queued', -- queued|running|done|failed
  result_json jsonb,
  error text,
  usage_tokens integer,
  cost_usd numeric(10,4),
  created_at timestamptz not null default now()
);

create index if not exists idx_runs_user_id on public.runs(user_id);
create index if not exists idx_runs_file_id on public.runs(file_id);
