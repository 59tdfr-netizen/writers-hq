-- Stage 2 of the private-avatar rollout.
-- Apply only after the signed-URL client is deployed and has passed two-account
-- verification. Never apply before the preflight migration and client rollout.
begin;

update public.profiles
set avatar_url = regexp_replace(
  avatar_url,
  '^https?://[^/]+/storage/v1/object/public/writer-avatars/',
  ''
)
where avatar_url ~ '^https?://[^/]+/storage/v1/object/public/writer-avatars/.+$';

-- Authenticated users may view profile avatars; ownership rules remain in place
-- for upload, update and delete operations.
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
