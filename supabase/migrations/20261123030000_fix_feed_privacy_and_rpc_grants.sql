-- Align the achievement feed with the privacy copy:
-- an author has opted in to show achievements to people who follow that author.
-- Therefore the viewer must be follower_id and the achievement owner followed_id.
create or replace function public.get_writer_achievement_feed()
returns table(
  event_id bigint,
  user_id uuid,
  display_name text,
  avatar_url text,
  social_url text,
  donation_url text,
  achievement_id text,
  earned_at timestamptz,
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
          where wf.follower_id = (select auth.uid())
            and wf.followed_id = e.user_id
        )
      )
    )
  order by e.earned_at desc, e.id desc
  limit 50;
$function$;

-- The client-facing privileged RPCs are intentional API endpoints, but they
-- must never be callable by anonymous users or via the implicit PUBLIC grant.
revoke all on function public.create_club_invitation(uuid, text, integer, integer) from public, anon, authenticated;
grant execute on function public.create_club_invitation(uuid, text, integer, integer) to authenticated;

revoke all on function public.get_registered_writer_count() from public, anon, authenticated;
grant execute on function public.get_registered_writer_count() to authenticated;

revoke all on function public.get_writer_achievement_feed() from public, anon, authenticated;
grant execute on function public.get_writer_achievement_feed() to authenticated;

revoke all on function public.get_writer_achievements(uuid) from public, anon, authenticated;
grant execute on function public.get_writer_achievements(uuid) to authenticated;

revoke all on function public.get_writer_stats(uuid) from public, anon, authenticated;
grant execute on function public.get_writer_stats(uuid) to authenticated;

revoke all on function public.get_writer_supporters(uuid) from public, anon, authenticated;
grant execute on function public.get_writer_supporters(uuid) to authenticated;

revoke all on function public.is_club_member(uuid) from public, anon, authenticated;
grant execute on function public.is_club_member(uuid) to authenticated;

revoke all on function public.redeem_invitation(text) from public, anon, authenticated;
grant execute on function public.redeem_invitation(text) to authenticated;

-- These functions are invoked only by database triggers, never by the API.
revoke all on function public.handle_new_user() from public, anon, authenticated;
revoke all on function public.sync_writer_achievement_events() from public, anon, authenticated;
