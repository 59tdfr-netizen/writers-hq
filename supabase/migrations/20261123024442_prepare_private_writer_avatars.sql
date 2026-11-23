-- Stage 1 of the private-avatar rollout.
-- This migration adds authenticated read access for signed URLs but keeps the
-- bucket public and leaves existing profile URLs unchanged.
drop policy if exists writer_avatars_select_authenticated on storage.objects;
create policy writer_avatars_select_authenticated
on storage.objects
for select
to authenticated
using (bucket_id = 'writer-avatars');
