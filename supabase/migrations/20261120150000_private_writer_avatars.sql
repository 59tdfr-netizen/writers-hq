-- Switch writer avatars to private storage.
-- Deploy the client code that resolves signed URLs before applying this migration.
-- The app stores object paths (not signed URLs) in profiles.avatar_url.

begin;

update public.profiles
set avatar_url = regexp_replace(
  avatar_url,
  '^https?://[^/]+/storage/v1/object/public/writer-avatars/',
  ''
)
where avatar_url ~ '^https?://[^/]+/storage/v1/object/public/writer-avatars/.+$';

-- Signed URLs are generated only for authenticated visitors. RLS must permit
-- authenticated users to read avatar objects owned by other users.
drop policy if exists writer_avatars_select_own on storage.objects;
drop policy if exists writer_avatars_select_authenticated on storage.objects;

create policy writer_avatars_select_authenticated
on storage.objects
for select
to authenticated
using (bucket_id = 'writer-avatars');

update storage.buckets
set public = false
where id = 'writer-avatars';

commit;
