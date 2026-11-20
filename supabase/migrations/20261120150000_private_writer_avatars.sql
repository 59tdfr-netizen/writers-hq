-- Stage 2 of the private-avatar rollout. Apply only AFTER the signed-URL client is deployed
-- and the preflight policy migration has been applied.
-- This normalizes old public URLs to object paths and then makes the bucket private.

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
