-- This helper only checks the current identity and target ID; it does not need
-- elevated privileges. Keep it as SECURITY INVOKER for the writer_likes RLS policy.
create or replace function public.can_like_writer(p_target_user_id uuid)
returns boolean
language sql
stable
security invoker
set search_path = ''
as $function$
  select
    (select auth.uid()) is not null
    and p_target_user_id is distinct from (select auth.uid());
$function$;
