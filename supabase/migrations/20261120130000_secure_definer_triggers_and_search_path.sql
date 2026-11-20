-- Harden trigger-only and normalization functions used by the public API.
-- Trigger functions do not need direct EXECUTE grants for end users after trigger creation.
alter function public.set_writer_opportunity_dedupe_keys()
  set search_path = '';

revoke all on function public.sync_writer_achievement_events()
  from public, anon, authenticated;
