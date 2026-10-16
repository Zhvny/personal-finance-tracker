# Backup Strategy — Alpha Finance Tracker

## Overview

PostgreSQL backup strategy using `pg_dump` with compressed custom format (`.sql.gz`), retention policy, and verification.

## Backup Types

### Full Backup
- **Frequency**: Daily at 02:00 UTC (via cron)
- **Tool**: `pg_dump -Fc` (custom compressed format)
- **Retention**: 30 days (configurable via `BACKUP_RETENTION_DAYS`)
- **Location**: `./backups/` directory (configurable via `BACKUP_DIR`)

### WAL Archiving (Future)
For point-in-time recovery (PITR), configure WAL archiving:
```sql
ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'gzip < %p > /backup/wal/%f.gz';
```

## Cron Schedule

```bash
# Daily full backup at 2 AM UTC
0 2 * * * cd /app && python scripts/tools/backup.py full

# Verify backups daily
0 3 * * * cd /app && python scripts/tools/backup.py verify

# Cleanup old backups weekly
0 4 * * 0 cd /app && python scripts/tools/backup.py cleanup
```

## Usage

```bash
# Create full backup
python scripts/tools/backup.py full

# List all backups
python scripts/tools/backup.py list

# Verify latest backup
python scripts/tools/backup.py verify

# Restore from backup (interactive, use with caution)
python scripts/tools/backup.py restore ./backups/full_backup_20260904_020000.sql.gz

# Manual cleanup
python scripts/tools/backup.py cleanup
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_HOST | localhost | Database host |
| POSTGRES_PORT | 5432 | Database port |
| POSTGRES_DB | finance_tracker | Database name |
| POSTGRES_USER | postgres | Database user |
| POSTGRES_PASSWORD | (required) | Database password |
| BACKUP_DIR | ./backups | Backup storage directory |
| BACKUP_RETENTION_DAYS | 30 | Days to retain backups |

## Backup Verification

Each backup creates a metadata file (`.metadata.json`) containing:
- Timestamp
- Size
- SHA256 checksum
- Compression type

Verification checks:
1. File exists
2. Checksum matches

## Restore Procedure

**WARNING: Restore will overwrite the current database. Use with caution!**

1. Stop all application services
2. Create a pre-restore backup (safety first)
3. Run restore:
   ```bash
   python scripts/tools/backup.py restore <backup_file>
   ```
4. Verify data integrity
5. Restart services

## Kubernetes Backup (Production)

For production k8s deployments, use a CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15-alpine
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -Fc -h postgres-db -U postgres finance_tracker > /backups/backup_$(date +%Y%m%d_%H%M%S).sql.gz
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-secret
                  key: POSTGRES_PASSWORD
            volumeMounts:
            - name: backup-storage
              mountPath: /backups
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

## Testing Restore

**IMPORTANT: Test restore quarterly in a non-production environment**

1. Create a test database
2. Restore backup to test database
3. Verify data integrity
4. Drop test database

```bash
# Test restore to separate database
PGPASSWORD=xxx pg_restore -h localhost -U postgres -d finance_tracker_test backup.sql.gz
```

## Checklist

- [ ] Verify cron job is scheduled
- [ ] Confirm backup directory has sufficient space
- [ ] Test restore procedure in non-production
- [ ] Set up off-site backup replication (S3/GCS/Azure Blob)
- [ ] Document restore time objectives (RTO/RPO)
