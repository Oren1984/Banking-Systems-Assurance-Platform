# SYNTHETIC MOCK BANKING SYSTEM — fake business-continuity/disaster-recovery job, not real code.
# Deliberate NEGATIVE example: clean scheduled backup/failover check.
# Expect: no findings from this file.


def run_daily_backup_and_failover_check(conn, backup_target):
    audit_log("backup_verified", actor="scheduler", action="backup_check", target=backup_target)
    return {"backup_target": backup_target, "status": "ok"}


def audit_log(event, actor, action, target):
    return {"event": event, "actor": actor, "action": action, "target": target}
