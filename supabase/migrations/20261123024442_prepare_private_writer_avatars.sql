-- Stage 1 of the private-avatar rollout.
-- This migration keeps the bucket public and leaves existing profile URLs unchanged.
-- It adds authenticated read access needed to request signed URLs.
drop policy if exists writer_avatars_select_authenticated on storage.objects;
create policy writer_avatars_select_authenticated
on storage.objects
for select
to authenticated
using (bucket_id = 'writer-avatars');
