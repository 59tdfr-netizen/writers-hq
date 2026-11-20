from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "database-backup.yml").read_text(encoding="utf-8")
DOCS = (ROOT / "docs" / "DATABASE_BACKUP.md").read_text(encoding="utf-8")


def main():
    assert 'cron: "17 2 * * *"' in WORKFLOW, "Daily backup schedule is missing."
    assert "workflow_dispatch:" in WORKFLOW, "Manual backup trigger is missing."
    assert "secrets.SUPABASE_DB_URL" in WORKFLOW, "Database URL must come from a repository secret."
    assert "secrets.BACKUP_AGE_PUBLIC_KEY" in WORKFLOW, "Encryption public key must come from a repository secret."
    assert "pg_dump" in WORKFLOW and "--format=custom" in WORKFLOW, "Expected a PostgreSQL custom-format dump."
    assert "pg_restore --list" in WORKFLOW, "Backup archive index validation is missing."
    assert "age --encrypt" in WORKFLOW, "Backup must be encrypted before artifact upload."
    assert "sha256sum writers-hq.dump.age > writers-hq.dump.age.sha256" in WORKFLOW, "Encrypted archive checksum must use a portable relative filename."
    assert "actions/upload-artifact@v4" in WORKFLOW, "Encrypted backup artifact upload is missing."
    assert "retention-days: 30" in WORKFLOW, "Backup artifact retention must be explicit."
    assert "Database backup was skipped" in WORKFLOW, "Missing secrets must be visible in the run summary."
    assert "does **not** include the actual bytes stored in Supabase Storage" in DOCS, "Storage backup limitation must remain documented."
    assert "does not prove a full Supabase project can be restored" in DOCS, "Restore limitation must remain documented."
    print("Backup workflow checks passed: schedule, secrets, dump validation, encryption, checksum, artifact retention, and limitations.")


if __name__ == "__main__":
    main()
