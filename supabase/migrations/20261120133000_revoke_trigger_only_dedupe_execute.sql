-- The dedupe function is intended to run only as a trigger.
-- Trigger execution does not require end users to have direct EXECUTE privileges.
revoke all on function public.set_writer_opportunity_dedupe_keys()
  from public, anon, authenticated;
