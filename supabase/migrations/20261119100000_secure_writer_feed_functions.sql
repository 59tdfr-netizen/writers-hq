
create or replace function public.sync_writer_achievement_events()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  achievement text;
begin
  if pg_catalog.jsonb_typeof(coalesce(new.diary_achievements, '[]'::jsonb)) = 'array' then
    for achievement in
      select pg_catalog.jsonb_array_elements_text(coalesce(new.diary_achievements, '[]'::jsonb))
    loop
      if pg_catalog.length(pg_catalog.btrim(achievement)) > 0 then
        insert into public.writer_achievement_events(user_id, achievement_id)
        values (new.user_id, achievement)
        on conflict (user_id, achievement_id) do nothing;
      end if;
    end loop;
  end if;
  return new;
end;
$$;

create or replace function public.get_writer_achievement_feed()
returns table (
  event_id bigint,
  user_id uuid,
  display_name text,
  avatar_url text,
  social_url text,
  donation_url text,
  achievement_id text,
  earned_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
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
  order by e.earned_at desc, e.id desc
  limit 50;
$$;

revoke all on function public.get_writer_achievement_feed() from public, anon;
grant execute on function public.get_writer_achievement_feed() to authenticated;
