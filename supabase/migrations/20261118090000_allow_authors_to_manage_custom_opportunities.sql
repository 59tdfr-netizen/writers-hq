alter table public.writer_opportunities
  add column if not exists created_by uuid references auth.users(id) on delete cascade;

create policy "writer_opportunities_insert_own"
  on public.writer_opportunities
  for insert
  to authenticated
  with check ((select auth.uid()) = created_by);

create policy "writer_opportunities_update_own"
  on public.writer_opportunities
  for update
  to authenticated
  using ((select auth.uid()) = created_by)
  with check ((select auth.uid()) = created_by);

create policy "writer_opportunities_delete_own"
  on public.writer_opportunities
  for delete
  to authenticated
  using ((select auth.uid()) = created_by);
