alter table public.writer_opportunities
  add column if not exists dedupe_url_key text,
  add column if not exists dedupe_title_deadline_key text;

create or replace function public.set_writer_opportunity_dedupe_keys()
returns trigger
language plpgsql
as $$
declare
  normalized_title text;
  normalized_url text;
begin
  normalized_title := regexp_replace(
    lower(btrim(coalesce(new.title, ''))),
    '[[:space:][:punct:]]+',
    '',
    'g'
  );

  normalized_url := nullif(
    regexp_replace(
      regexp_replace(lower(btrim(coalesce(new.source_url, ''))), '[?#].*$', ''),
      '/+$',
      ''
    ),
    ''
  );

  new.dedupe_url_key := normalized_url;
  new.dedupe_title_deadline_key := case
    when normalized_title = '' then null
    else normalized_title || '|' || coalesce(new.deadline::text, 'no-deadline')
  end;

  return new;
end;
$$;

drop trigger if exists writer_opportunities_set_dedupe_keys
  on public.writer_opportunities;

create trigger writer_opportunities_set_dedupe_keys
before insert or update on public.writer_opportunities
for each row
execute function public.set_writer_opportunity_dedupe_keys();

update public.writer_opportunities
set title = title;

create unique index if not exists writer_opportunities_dedupe_url_key_uidx
  on public.writer_opportunities (dedupe_url_key)
  where dedupe_url_key is not null;

create unique index if not exists writer_opportunities_dedupe_title_deadline_uidx
  on public.writer_opportunities (dedupe_title_deadline_key)
  where dedupe_title_deadline_key is not null;
