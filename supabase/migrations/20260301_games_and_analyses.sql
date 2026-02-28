-- =============================================================
-- games: 棋譜保存
-- =============================================================
create table if not exists public.games (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references auth.users(id) on delete set null,   -- NULL = 未ログイン
  title         text,
  kifu_text     text not null,
  kifu_format   text not null check (kifu_format in ('kif', 'csa', 'usi')),
  move_count    integer,
  created_at    timestamptz not null default now()
);

alter table public.games enable row level security;

-- 全員読み取り可
create policy "games_select_public"
on public.games for select
using (true);

-- ログインユーザーは自分の棋譜のみ、または未ログイン(user_id IS NULL)も INSERT 可
create policy "games_insert"
on public.games for insert
with check (
  user_id is null
  or user_id = auth.uid()
);

create policy "games_update"
on public.games for update
using (user_id = auth.uid())
with check (user_id = auth.uid());

create policy "games_delete"
on public.games for delete
using (user_id = auth.uid());

create index if not exists idx_games_user_id on public.games (user_id);

-- =============================================================
-- analyses: エンジン解析結果
-- =============================================================
create table if not exists public.analyses (
  id          uuid primary key default gen_random_uuid(),
  game_id     uuid not null references public.games(id) on delete cascade,
  engine_name text not null default 'yaneuraou',
  depth       integer,
  nodes       jsonb,   -- 全手の評価値・PV・delta
  summary     jsonb,   -- サマリ情報
  created_at  timestamptz not null default now()
);

alter table public.analyses enable row level security;

create policy "analyses_select"
on public.analyses for select
using (
  exists (
    select 1 from public.games g
    where g.id = game_id
  )
);

create policy "analyses_insert"
on public.analyses for insert
with check (
  exists (
    select 1 from public.games g
    where g.id = game_id
      and (g.user_id is null or g.user_id = auth.uid())
  )
);

create policy "analyses_delete"
on public.analyses for delete
using (
  exists (
    select 1 from public.games g
    where g.id = game_id
      and g.user_id = auth.uid()
  )
);

create index if not exists idx_analyses_game_id on public.analyses (game_id);

-- =============================================================
-- explanations: 解説文（手ごと）
-- =============================================================
create table if not exists public.explanations (
  id               uuid primary key default gen_random_uuid(),
  analysis_id      uuid not null references public.analyses(id) on delete cascade,
  ply              integer not null,
  explanation_json jsonb not null,
  model_used       text,
  created_at       timestamptz not null default now()
);

alter table public.explanations enable row level security;

create policy "explanations_select"
on public.explanations for select
using (
  exists (
    select 1 from public.analyses a
    join public.games g on g.id = a.game_id
    where a.id = analysis_id
  )
);

create policy "explanations_insert"
on public.explanations for insert
with check (
  exists (
    select 1 from public.analyses a
    join public.games g on g.id = a.game_id
    where a.id = analysis_id
      and (g.user_id is null or g.user_id = auth.uid())
  )
);

create policy "explanations_delete"
on public.explanations for delete
using (
  exists (
    select 1 from public.analyses a
    join public.games g on g.id = a.game_id
    where a.id = analysis_id
      and g.user_id = auth.uid()
  )
);

create index if not exists idx_explanations_analysis_id on public.explanations (analysis_id);
create index if not exists idx_explanations_analysis_ply on public.explanations (analysis_id, ply);
