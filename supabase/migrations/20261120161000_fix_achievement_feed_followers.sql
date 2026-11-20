-- Show opted-in achievement events to the authors who follow the event author,
-- matching the wording in the profile privacy setting.
-- The previous predicate checked the opposite follow direction.

create or replace function public.get_writer_achievement_feed()
returns table(
  event_id bigint,
  user_id uuid,
  display_name text,
  avatar_url text,
  social_url text,
  donation_url text,
  achievement_id text,
  earned_at timestamp with time zone
)
language sql
stable
security definer
set search_path to ''
as $function$
  select
    e.id,
    e.user_id,
    coalesce(p.display_name, 'Автор'),
    p.avatar_url,
    p.social_url,
    p.donation_url,
    e.achievement_id,
    e.earned_at
  from public.writer_achievement_events e
  join public.writer_settings s on s.user_id = e.user_id
  join public.profiles p on p.id = e.user_id
  where (select auth.uid()) is not null
    and e.user_id <> (select auth.uid())
    and s.show_stats_to_mutuals is true
    and exists (
      select 1
      from public.writer_follows wf
      where wf.follower_id = e.user_id
        and wf.followed_id = (select auth.uid())
    )
  order by e.earned_at desc, e.id desc
  limit 50;
$function$;
