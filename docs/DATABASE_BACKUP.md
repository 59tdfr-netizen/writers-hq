# Database backup and recovery

## What this protects

The GitHub Actions workflow `.github/workflows/database-backup.yml` creates a PostgreSQL custom-format dump, checks that PostgreSQL can read its archive index, encrypts it with age, and uploads only the encrypted file as a GitHub Actions artifact. It runs daily at 02:17 UTC and can also be started manually from **Actions → Encrypted database backup → Run workflow**.

The backup includes PostgreSQL database contents available to the configured database role. It does **not** include the actual bytes stored in Supabase Storage (such as avatar image files), GitHub repository files, or Supabase project configuration. Those need separate recovery procedures.

Artifacts are retained for 30 days. This is a first recovery layer, not a complete disaster-recovery arrangement: GitHub and Supabase are still separate services, but a GitHub account/repository outage could affect access to these artifacts. Add a second encrypted destination before relying on this for long-term production recovery.

## One-time setup

1. Install age on a trusted computer and generate a key pair: `age-keygen -o writers-hq-backup-key.txt`.
2. Keep `writers-hq-backup-key.txt` offline in a secure place. **Never commit or upload the private key.** Losing it means the encrypted backups cannot be decrypted.
3. Copy the public recipient (the line beginning `age1...`) from the generated file.
4. In GitHub, open **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `BACKUP_AGE_PUBLIC_KEY`: the public `age1...` recipient.
   - `SUPABASE_DB_URL`: the PostgreSQL connection string for this Supabase project. Use a connection mode supported for long-running database tools such as `pg_dump`; do not use the Supabase anon/publishable key or service-role key.
5. Run **Actions → Encrypted database backup → Run workflow**.
6. Confirm the run completed and that the uploaded artifact contains only `writers-hq.dump.age` and its checksum. If secrets are missing, the workflow intentionally skips the backup and emits a warning.

Treat the database URL as a password: never paste it into issues, pull requests, chat messages, or workflow logs.

## Recovery outline

1. Download the encrypted artifact from a trusted session.
2. Verify its encrypted-file checksum with `sha256sum -c writers-hq.dump.age.sha256`.
3. Decrypt it locally with the offline private key, for example: `age --decrypt --identity writers-hq-backup-key.txt --output writers-hq.dump writers-hq.dump.age`.
4. Validate the archive with `pg_restore --list writers-hq.dump`.
5. Restore into a **separate, empty recovery project** first. Supabase-managed roles, extensions, and system schemas can make a direct full-database restore unsuitable without adjustments. Do not restore over production until the recovery has been rehearsed and checked.

A successful `pg_dump` and archive-list check proves that a dump was produced and is readable; it does not prove a full Supabase project can be restored. A recovery drill and a separate backup of Storage objects are still required.
