-- Expose aggregate achievement likes and allow authors to see their own liked achievements.
-- Names of likers are not returned; the client resolves ids to profile avatars only.

drop function if exists public.get_writer_achievement_feed();

create function public.get_writer_achievement_feed()
returns table (
  event_id bigint,
  user_id uuid,
  display_name text,
  avatar_url text,
  social_url text,
  donation_url text,
  achievement_id text,
  earned_at timestamp with time zone,
  like_count bigint,
  liker_ids uuid[]
)
language sql
stable
security definer
set search_path = ''
as $function$
  select
    e.id,
    e.user_id,
    coalesce(p.display_name, 'Автор'),
    p.avatar_url,
    p.social_url,
    p.donation_url,
    e.achievement_id,
    e.earned_at,
    coalesce(likes.like_count, 0),
    coalesce(likes.liker_ids, array[]::uuid[])
  from public.writer_achievement_events e
  join public.writer_settings s on s.user_id = e.user_id
  join public.profiles p on p.id = e.user_id
  left join lateral (
    select
      count(*)::bigint as like_count,
      array_agg(wl.liker_id order by wl.created_at desc) as liker_ids
    from public.writer_likes wl
    where wl.target_user_id = e.user_id
      and wl.item_type = 'achievement'
      and wl.achievement_id = e.achievement_id
  ) likes on true
  where (select auth.uid()) is not null
    and (
      (
        e.user_id = (select auth.uid())
        and coalesce(likes.like_count, 0) > 0
      )
      or (
        e.user_id <> (select auth.uid())
        and s.show_stats_to_mutuals is true
        and exists (
          select 1
          from public.writer_follows wf
          where wf.follower_id = e.user_id
            and wf.followed_id = (select auth.uid())
        )
      )
    )
  order by e.earned_at desc, e.id desc
  limit 50;
$function$;

revoke all on function public.get_writer_achievement_feed() from public, anon;
grant execute on function public.get_writer_achievement_feed() to authenticated;
