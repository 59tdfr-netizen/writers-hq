from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "database-backup.yml").read_text(encoding="utf-8")
DOCS = (ROOT / "docs" / "DATABASE_BACKUP.md").read_text(encoding="utf-8")
UPTIME = (ROOT / ".github" / "workflows" / "site-availability.yml").read_text(encoding="utf-8")
LINK_CHECK = (ROOT / ".github" / "workflows" / "contest-link-health.yml").read_text(encoding="utf-8")
LINK_SCRIPT = (ROOT / "scripts" / "check_contest_links.py").read_text(encoding="utf-8")


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
    assert 'cron: "43 7 * * *"' in UPTIME, "Daily public-site availability check is missing."
    assert "workflow_dispatch:" in UPTIME, "Manual public-site availability check is missing."
    assert "curl --fail" in UPTIME, "Availability check must fail on HTTP errors."
    assert "assets/favicon.svg" in UPTIME, "Availability check must verify the favicon asset."
    assert 'cron: "31 8 * * 1"' in LINK_CHECK, "Weekly link check schedule missing."
    assert 'LINK_CHECK_LIMIT: "25"' in LINK_CHECK, "Link checker must be bounded."
    assert "secrets.SUPABASE_SERVICE_ROLE_KEY" in LINK_CHECK, "Service key must come from a secret."
    assert "LIMIT = min(25" in LINK_SCRIPT, "Hard record cap missing."
    assert "time.sleep(pause)" in LINK_SCRIPT, "Per-host rate limit missing."
    assert "exc.code in (405, 501)" in LINK_SCRIPT, "HEAD fallback missing."
    assert "return 1 if broken else 0" in LINK_SCRIPT, "Only confirmed broken links should fail."
    print("Workflow checks passed: encrypted backups, site availability and contest link health.")


if __name__ == "__main__":
    main()
