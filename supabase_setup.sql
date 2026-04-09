-- ============================================================
-- EBOOK TOOL — Supabase Database Setup
-- Run this once in your Supabase SQL Editor
-- ============================================================

-- ── Projects Table ────────────────────────────────────────────
-- Stores every project the user saves (full form config as JSON)
create table if not exists projects (
  id         uuid primary key default gen_random_uuid(),
  name       text not null default 'Untitled Project',
  config     jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Auto-update updated_at on every row change
create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists projects_updated_at on projects;
create trigger projects_updated_at
  before update on projects
  for each row execute procedure update_updated_at();

-- ── Settings Table ────────────────────────────────────────────
-- Key-value store for persistent app-level settings
-- e.g. default_group_link
create table if not exists settings (
  id         serial primary key,
  key        text unique not null,
  value      text,
  updated_at timestamptz not null default now()
);

-- Seed the default footer/QR link (change value as needed)
insert into settings (key, value)
values ('default_group_link', 'https://facebook.com/groups/hidden-shelf')
on conflict (key) do nothing;

-- ── Row Level Security (optional but recommended) ─────────────
-- Uncomment if you want per-user isolation later
-- alter table projects enable row level security;
-- alter table settings  enable row level security;

-- ── Done ──────────────────────────────────────────────────────
-- Tables: projects, settings
-- Endpoints available after deploying backend:
--
--   GET    /api/health              → check if backend + supabase alive
--   POST   /api/generate            → generate PDF
--
--   POST   /api/projects            → save project
--   GET    /api/projects            → list all projects
--   GET    /api/projects/<id>       → load one project
--   PUT    /api/projects/<id>       → update project
--   DELETE /api/projects/<id>       → delete project
--
--   GET    /api/settings            → read all settings
--   PUT    /api/settings            → update settings (e.g. default_group_link)
