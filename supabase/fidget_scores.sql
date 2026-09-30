-- Fidget scoreboard table for tanishmaheshwary.com
-- Run once in Supabase: SQL Editor > New query > paste > Run.

create table if not exists public.fidget_scores (
  id         bigint generated always as identity primary key,
  name       text        not null check (char_length(name) between 1 and 10 and name ~ '^[A-Z0-9 ._-]+$'),
  score      integer     not null check (score between 1 and 999),
  created_at timestamptz not null default now()
);

create index if not exists fidget_scores_top on public.fidget_scores (score desc, created_at asc);

-- Visitors may read scores and add new ones. Nobody can edit or delete (only you, from the dashboard).
alter table public.fidget_scores enable row level security;

drop policy if exists "read scores" on public.fidget_scores;
create policy "read scores" on public.fidget_scores for select to anon using (true);

drop policy if exists "add a score" on public.fidget_scores;
create policy "add a score" on public.fidget_scores for insert to anon with check (true);
