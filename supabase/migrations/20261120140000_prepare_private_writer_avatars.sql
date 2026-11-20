-- Stage 1 of the private-avatar rollout.
-- Apply this migration BEFORE deploying the signed-URL client.
-- It allows authenticated users to request signed URLs for other authors'
-- avatars while the bucket remains public and existing profile URLs remain unchanged.
-- This migration does NOT make the bucket private.

drop policy if exists writer_avatars_select_authenticated on storage.objects;

create policy writer_avatars_select_authenticated
on storage.objects
for select
to authenticated
using (bucket_id = 'writer-avatars');
