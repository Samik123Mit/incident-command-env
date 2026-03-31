"""Task scenarios for the Incident Command environment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class TaskScenario:
    task_id: str
    name: str
    difficulty: str
    incident_summary: str
    initial_alerts: List[Dict[str, Any]]
    services: Dict[str, Dict[str, Any]]
    log_bank: Dict[str, List[Dict[str, Any]]]
    metric_bank: Dict[str, List[Dict[str, Any]]]
    root_cause_service: str
    root_cause_keywords: List[str]
    required_remediation: List[str]
    optimal_action_sequence: List[str]
    max_steps: int = 20
    red_herring_services: List[str] = field(default_factory=list)


def _alert(aid, sev, svc, title, msg, ts, firing=True):
    return dict(alert_id=aid, severity=sev, service=svc, title=title, message=msg, timestamp=ts, is_firing=firing)

def _log(ts, svc, lvl, msg):
    return dict(timestamp=ts, service=svc, level=lvl, message=msg)

def _metric(ts, svc, name, val, unit):
    return dict(timestamp=ts, service=svc, metric_name=name, value=val, unit=unit)

def _svc(name, status, uptime, cpu, mem, run, desired, deploy_ts, sha):
    return dict(name=name, status=status, uptime_seconds=uptime, cpu_percent=cpu,
                memory_percent=mem, replicas_running=run, replicas_desired=desired,
                last_deploy=deploy_ts, last_deploy_sha=sha)


def build_easy_task() -> TaskScenario:
    return TaskScenario(
        task_id="easy_oom_kill",
        name="OOM Kill: Web Server Memory Leak",
        difficulty="easy",
        incident_summary="PagerDuty alert: web-api pods restarting repeatedly. Users reporting 502 errors on the dashboard. Started ~10 minutes ago.",
        initial_alerts=[
            _alert("ALT-001", "critical", "web-api", "Pod OOMKilled",
                   "web-api-7f8b4d-xk9m2 OOMKilled. Container exceeded 2Gi memory limit. Restart count: 5 in last 10 min.",
                   "2026-03-31T14:52:00Z"),
            _alert("ALT-002", "warning", "web-api", "High 5xx Rate",
                   "web-api 5xx rate at 34% (threshold: 5%). Sustained for 8 minutes.",
                   "2026-03-31T14:50:00Z"),
        ],
        services={
            "web-api": _svc("web-api", "degraded", 180, 12.5, 97.3, 1, 3, "2026-03-31T10:00:00Z", "a1b2c3d"),
            "postgres-primary": _svc("postgres-primary", "healthy", 864000, 22.0, 45.0, 1, 1, "2026-03-20T08:00:00Z", "e4f5g6h"),
            "redis-cache": _svc("redis-cache", "healthy", 432000, 5.0, 30.0, 1, 1, "2026-03-25T12:00:00Z", "i7j8k9l"),
        },
        log_bank={
            "web-api": [
                _log("2026-03-31T14:42:00Z", "web-api", "INFO", "Request processed: GET /api/dashboard 200 45ms"),
                _log("2026-03-31T14:43:00Z", "web-api", "WARN", "Memory usage at 78% of limit (2Gi). GC pressure increasing."),
                _log("2026-03-31T14:44:00Z", "web-api", "WARN", "Memory usage at 85% of limit. Large object cache growing: user_session_cache size=1.2Gi"),
                _log("2026-03-31T14:45:00Z", "web-api", "ERROR", "Memory usage at 93%. user_session_cache not evicting expired entries. Possible memory leak in SessionManager.get_or_create()"),
                _log("2026-03-31T14:46:00Z", "web-api", "ERROR", "java.lang.OutOfMemoryError: Java heap space at com.app.session.SessionManager.get_or_create(SessionManager.java:142)"),
                _log("2026-03-31T14:47:00Z", "web-api", "ERROR", "Container OOMKilled by kubelet. Exit code 137. Restarting..."),
                _log("2026-03-31T14:48:00Z", "web-api", "INFO", "web-api starting up... memory baseline: 512Mi"),
                _log("2026-03-31T14:50:00Z", "web-api", "WARN", "Memory usage climbing rapidly: 1.4Gi after 120s uptime. SessionManager leak persists."),
                _log("2026-03-31T14:52:00Z", "web-api", "ERROR", "Container OOMKilled again. 5th restart in 10 minutes."),
            ],
            "postgres-primary": [
                _log("2026-03-31T14:45:00Z", "postgres-primary", "INFO", "Checkpoint complete: wrote 234 buffers (1.4%)"),
                _log("2026-03-31T14:50:00Z", "postgres-primary", "INFO", "Connection count: 45/200. All healthy."),
            ],
            "redis-cache": [
                _log("2026-03-31T14:45:00Z", "redis-cache", "INFO", "Memory usage: 614Mi/2Gi. Eviction policy: allkeys-lru. 0 evictions."),
            ],
        },
        metric_bank={
            "web-api": [
                _metric("2026-03-31T14:40:00Z", "web-api", "memory_usage_bytes", 1073741824, "bytes"),
                _metric("2026-03-31T14:42:00Z", "web-api", "memory_usage_bytes", 1503238553, "bytes"),
                _metric("2026-03-31T14:44:00Z", "web-api", "memory_usage_bytes", 1825361101, "bytes"),
                _metric("2026-03-31T14:46:00Z", "web-api", "memory_usage_bytes", 2147483648, "bytes"),
                _metric("2026-03-31T14:40:00Z", "web-api", "http_5xx_rate", 0.01, "ratio"),
                _metric("2026-03-31T14:46:00Z", "web-api", "http_5xx_rate", 0.34, "ratio"),
                _metric("2026-03-31T14:52:00Z", "web-api", "http_5xx_rate", 0.41, "ratio"),
                _metric("2026-03-31T14:40:00Z", "web-api", "restart_count", 0, "count"),
                _metric("2026-03-31T14:52:00Z", "web-api", "restart_count", 5, "count"),
            ],
            "postgres-primary": [
                _metric("2026-03-31T14:50:00Z", "postgres-primary", "connection_count", 45, "count"),
                _metric("2026-03-31T14:50:00Z", "postgres-primary", "query_latency_p99", 12.5, "ms"),
            ],
            "redis-cache": [
                _metric("2026-03-31T14:50:00Z", "redis-cache", "memory_usage_bytes", 643825664, "bytes"),
                _metric("2026-03-31T14:50:00Z", "redis-cache", "hit_rate", 0.94, "ratio"),
            ],
        },
        root_cause_service="web-api",
        root_cause_keywords=["memory", "leak", "session", "oom"],
        required_remediation=["restart_service"],
        optimal_action_sequence=["check_service_status", "query_logs:web-api", "check_metrics:web-api", "identify_root_cause", "restart_service:web-api", "resolve_incident"],
        max_steps=15,
    )


def build_medium_task() -> TaskScenario:
    return TaskScenario(
        task_id="medium_connection_pool",
        name="Connection Pool Exhaustion: Database Bottleneck",
        difficulty="medium",
        incident_summary="PagerDuty alert: Multiple services reporting database timeouts. User-facing latency spiked 10x in the last 15 minutes. payment-service and order-service both affected. A deploy to order-service went out 20 minutes ago.",
        initial_alerts=[
            _alert("ALT-101", "critical", "payment-service", "Database Timeout Spike",
                   "payment-service p99 DB latency at 12.4s (threshold: 500ms). 67% of queries timing out.", "2026-03-31T15:10:00Z"),
            _alert("ALT-102", "critical", "order-service", "Connection Pool Exhausted",
                   "order-service: HikariPool-1 - Connection is not available, request timed out after 30000ms.", "2026-03-31T15:08:00Z"),
            _alert("ALT-103", "warning", "notification-service", "Elevated Error Rate",
                   "notification-service error rate at 8% (threshold 2%). Upstream dependency errors.", "2026-03-31T15:12:00Z"),
        ],
        services={
            "order-service": _svc("order-service", "degraded", 1200, 85.0, 62.0, 3, 3, "2026-03-31T14:50:00Z", "d3pl0y1"),
            "payment-service": _svc("payment-service", "degraded", 259200, 15.0, 40.0, 2, 2, "2026-03-28T09:00:00Z", "p4ym3nt"),
            "notification-service": _svc("notification-service", "degraded", 604800, 8.0, 25.0, 2, 2, "2026-03-24T11:00:00Z", "n0t1fy"),
            "postgres-primary": _svc("postgres-primary", "degraded", 2592000, 95.0, 78.0, 1, 1, "2026-03-01T08:00:00Z", "pg14"),
        },
        log_bank={
            "order-service": [
                _log("2026-03-31T14:55:00Z", "order-service", "INFO", "Deploy d3pl0y1 rolled out. Changes: added bulk order processing endpoint /api/v2/orders/bulk"),
                _log("2026-03-31T14:56:00Z", "order-service", "INFO", "Bulk order endpoint processing first batch: 500 orders"),
                _log("2026-03-31T14:57:00Z", "order-service", "WARN", "Connection pool utilization at 80% (40/50). Bulk processor holding connections during batch commit."),
                _log("2026-03-31T14:59:00Z", "order-service", "ERROR", "HikariPool-1: Connection not available after 30000ms. Active: 50/50. Waiting: 23. Bulk processor not releasing connections."),
                _log("2026-03-31T15:00:00Z", "order-service", "ERROR", "BulkOrderProcessor.processBatch() holds connection for entire batch (avg 45s). Missing connection.close() in finally block at BulkOrderProcessor.java:287"),
                _log("2026-03-31T15:02:00Z", "order-service", "ERROR", "All 50 connections exhausted. New requests queuing. Connection leak detected: 12 connections held > 60s."),
                _log("2026-03-31T15:05:00Z", "order-service", "ERROR", "Database connection timeout cascade. Postgres reports max_connections (200) from order-service pool drain."),
            ],
            "payment-service": [
                _log("2026-03-31T15:05:00Z", "payment-service", "WARN", "DB query latency spike: 8.2s for simple SELECT. Connection acquisition taking 7.5s."),
                _log("2026-03-31T15:08:00Z", "payment-service", "ERROR", "Cannot acquire DB connection from pool within 10s. Postgres seems overloaded."),
                _log("2026-03-31T15:10:00Z", "payment-service", "ERROR", "Payment processing failed for 145 transactions. DB connection timeout."),
            ],
            "notification-service": [
                _log("2026-03-31T15:10:00Z", "notification-service", "WARN", "Upstream call to order-service timing out: GET /api/orders/status 504 after 30s"),
                _log("2026-03-31T15:12:00Z", "notification-service", "ERROR", "Failed to fetch order details for email notification. Retrying 3/3."),
            ],
            "postgres-primary": [
                _log("2026-03-31T15:00:00Z", "postgres-primary", "WARN", "Connection count rising: 165/200. Most from order-service pool."),
                _log("2026-03-31T15:03:00Z", "postgres-primary", "ERROR", "FATAL: remaining connection slots reserved for superuser. 198/200 connections in use."),
                _log("2026-03-31T15:05:00Z", "postgres-primary", "WARN", "Long-running transactions detected: 12 transactions idle in transaction > 60s, all from order-service."),
            ],
        },
        metric_bank={
            "order-service": [
                _metric("2026-03-31T14:50:00Z", "order-service", "db_pool_active", 5, "count"),
                _metric("2026-03-31T14:57:00Z", "order-service", "db_pool_active", 40, "count"),
                _metric("2026-03-31T15:00:00Z", "order-service", "db_pool_active", 50, "count"),
                _metric("2026-03-31T15:05:00Z", "order-service", "db_pool_active", 50, "count"),
                _metric("2026-03-31T14:50:00Z", "order-service", "request_latency_p99", 0.12, "seconds"),
                _metric("2026-03-31T15:05:00Z", "order-service", "request_latency_p99", 32.5, "seconds"),
            ],
            "payment-service": [
                _metric("2026-03-31T14:50:00Z", "payment-service", "db_query_latency_p99", 0.015, "seconds"),
                _metric("2026-03-31T15:08:00Z", "payment-service", "db_query_latency_p99", 12.4, "seconds"),
                _metric("2026-03-31T15:08:00Z", "payment-service", "failed_transactions", 145, "count"),
            ],
            "postgres-primary": [
                _metric("2026-03-31T14:50:00Z", "postgres-primary", "active_connections", 65, "count"),
                _metric("2026-03-31T15:00:00Z", "postgres-primary", "active_connections", 165, "count"),
                _metric("2026-03-31T15:05:00Z", "postgres-primary", "active_connections", 198, "count"),
                _metric("2026-03-31T15:05:00Z", "postgres-primary", "idle_in_transaction", 12, "count"),
            ],
        },
        root_cause_service="order-service",
        root_cause_keywords=["connection", "leak", "pool", "bulk", "deploy", "d3pl0y1"],
        required_remediation=["rollback_deploy"],
        optimal_action_sequence=["check_service_status", "query_logs:order-service", "query_logs:postgres-primary", "check_metrics:order-service", "check_metrics:postgres-primary", "identify_root_cause", "rollback_deploy:order-service", "resolve_incident"],
        max_steps=20,
        red_herring_services=["notification-service"],
    )


def build_hard_task() -> TaskScenario:
    return TaskScenario(
        task_id="hard_cascading_failure",
        name="Cascading Failure: Deploy-Triggered Multi-Service Outage",
        difficulty="hard",
        incident_summary="SEV-1 incident: Complete checkout flow down. Multiple services degraded simultaneously. monitoring-service flagging CPU alerts on search-service, but user reports point to checkout and payment failures. Two deploys happened in the last hour: auth-service (35min ago) and search-service (10min ago). All hands on deck.",
        initial_alerts=[
            _alert("ALT-201", "critical", "search-service", "CPU Saturation",
                   "search-service CPU at 98%. Autoscaler maxed at 5/5 replicas. Response times > 15s.", "2026-03-31T16:20:00Z"),
            _alert("ALT-202", "critical", "checkout-service", "Checkout Failures",
                   "checkout-service: 78% of checkout attempts failing. Users cannot complete purchases.", "2026-03-31T16:18:00Z"),
            _alert("ALT-203", "critical", "payment-service", "Payment Timeouts",
                   "payment-service: upstream auth validation timing out for 90% of requests.", "2026-03-31T16:15:00Z"),
            _alert("ALT-204", "warning", "search-service", "High Memory Usage",
                   "search-service memory at 89%. May be approaching OOM.", "2026-03-31T16:22:00Z"),
            _alert("ALT-205", "warning", "auth-service", "Elevated Latency",
                   "auth-service p99 latency at 4.2s (baseline: 50ms). Token validation slow.", "2026-03-31T16:10:00Z"),
        ],
        services={
            "auth-service": _svc("auth-service", "degraded", 2100, 45.0, 55.0, 3, 3, "2026-03-31T15:45:00Z", "auth-v2.3.1"),
            "search-service": _svc("search-service", "degraded", 600, 98.0, 89.0, 5, 5, "2026-03-31T16:10:00Z", "srch-v1.8"),
            "checkout-service": _svc("checkout-service", "degraded", 604800, 30.0, 40.0, 3, 3, "2026-03-24T14:00:00Z", "chk-v3.1"),
            "payment-service": _svc("payment-service", "degraded", 259200, 20.0, 35.0, 2, 2, "2026-03-28T09:00:00Z", "pay-v4.2"),
            "postgres-primary": _svc("postgres-primary", "healthy", 2592000, 30.0, 50.0, 1, 1, "2026-03-01T08:00:00Z", "pg14"),
        },
        log_bank={
            "auth-service": [
                _log("2026-03-31T15:45:00Z", "auth-service", "INFO", "Deploy auth-v2.3.1 rolled out. Changes: migrated token validation from HS256 to RS256 for security compliance."),
                _log("2026-03-31T15:46:00Z", "auth-service", "INFO", "RS256 token validation active. Loading RSA public key from vault."),
                _log("2026-03-31T15:50:00Z", "auth-service", "WARN", "Token validation latency increased: RS256 verify avg 180ms vs HS256 avg 2ms. Expected but monitoring."),
                _log("2026-03-31T16:00:00Z", "auth-service", "WARN", "Token validation p99 at 850ms under load. RSA key not being cached -- fetching from vault on every request."),
                _log("2026-03-31T16:05:00Z", "auth-service", "ERROR", "Vault rate limit hit. RSA key fetch failing intermittently. Token validation falling back to synchronous retry with 2s timeout."),
                _log("2026-03-31T16:08:00Z", "auth-service", "ERROR", "Token validation p99 at 3.8s. All downstream services calling /auth/validate are experiencing timeouts."),
                _log("2026-03-31T16:10:00Z", "auth-service", "ERROR", "Cascading effect: payment-service, checkout-service all retrying auth calls. Request amplification: 3x normal auth volume."),
            ],
            "search-service": [
                _log("2026-03-31T16:10:00Z", "search-service", "INFO", "Deploy srch-v1.8 rolled out. Changes: upgraded elasticsearch client, added new product ranking algorithm."),
                _log("2026-03-31T16:12:00Z", "search-service", "WARN", "New ranking algorithm CPU-intensive. Processing time per query: 450ms (was 80ms)."),
                _log("2026-03-31T16:15:00Z", "search-service", "WARN", "CPU at 92%. Autoscaler triggered: scaling from 3 to 5 replicas."),
                _log("2026-03-31T16:18:00Z", "search-service", "ERROR", "CPU saturated at 98% even with 5 replicas. Query queue depth: 2,340. NOTE: search-service does NOT call auth-service. This is an independent issue."),
                _log("2026-03-31T16:20:00Z", "search-service", "ERROR", "Response times > 15s. Some queries timing out completely."),
            ],
            "checkout-service": [
                _log("2026-03-31T16:10:00Z", "checkout-service", "WARN", "Auth validation for checkout tokens taking 3.5s (normally 50ms). Calling auth-service /auth/validate."),
                _log("2026-03-31T16:12:00Z", "checkout-service", "ERROR", "Checkout flow timeout: auth validation + payment processing exceeding 30s request timeout."),
                _log("2026-03-31T16:15:00Z", "checkout-service", "ERROR", "78% of checkouts failing. Root call chain: checkout -> auth-service/validate (timeout) -> payment-service/charge (never reached)."),
                _log("2026-03-31T16:18:00Z", "checkout-service", "ERROR", "Retrying auth calls amplifying load on auth-service. Circuit breaker should have tripped but threshold set too high (90% error rate)."),
            ],
            "payment-service": [
                _log("2026-03-31T16:10:00Z", "payment-service", "WARN", "Pre-charge auth validation call to auth-service taking 3.2s (normally 40ms)."),
                _log("2026-03-31T16:13:00Z", "payment-service", "ERROR", "Auth validation timeout (5s) for 90% of payment attempts. Cannot verify user tokens."),
                _log("2026-03-31T16:15:00Z", "payment-service", "ERROR", "Payment failures: 342 failed charges in last 5 min. All due to auth-service timeout, not payment gateway issues."),
            ],
            "postgres-primary": [
                _log("2026-03-31T16:15:00Z", "postgres-primary", "INFO", "Database operating normally. Connection count: 80/200. Query latency nominal."),
            ],
        },
        metric_bank={
            "auth-service": [
                _metric("2026-03-31T15:44:00Z", "auth-service", "token_validation_p99", 0.045, "seconds"),
                _metric("2026-03-31T15:50:00Z", "auth-service", "token_validation_p99", 0.180, "seconds"),
                _metric("2026-03-31T16:00:00Z", "auth-service", "token_validation_p99", 0.850, "seconds"),
                _metric("2026-03-31T16:05:00Z", "auth-service", "token_validation_p99", 2.400, "seconds"),
                _metric("2026-03-31T16:10:00Z", "auth-service", "token_validation_p99", 4.200, "seconds"),
                _metric("2026-03-31T16:10:00Z", "auth-service", "vault_rate_limit_hits", 47, "count"),
                _metric("2026-03-31T16:10:00Z", "auth-service", "request_volume", 15000, "rpm"),
            ],
            "search-service": [
                _metric("2026-03-31T16:09:00Z", "search-service", "cpu_percent", 35.0, "percent"),
                _metric("2026-03-31T16:15:00Z", "search-service", "cpu_percent", 92.0, "percent"),
                _metric("2026-03-31T16:20:00Z", "search-service", "cpu_percent", 98.0, "percent"),
                _metric("2026-03-31T16:20:00Z", "search-service", "query_latency_p99", 15.2, "seconds"),
            ],
            "checkout-service": [
                _metric("2026-03-31T16:00:00Z", "checkout-service", "checkout_success_rate", 0.99, "ratio"),
                _metric("2026-03-31T16:15:00Z", "checkout-service", "checkout_success_rate", 0.22, "ratio"),
                _metric("2026-03-31T16:15:00Z", "checkout-service", "auth_call_latency_p99", 3.5, "seconds"),
            ],
            "payment-service": [
                _metric("2026-03-31T16:00:00Z", "payment-service", "payment_success_rate", 0.997, "ratio"),
                _metric("2026-03-31T16:15:00Z", "payment-service", "payment_success_rate", 0.10, "ratio"),
                _metric("2026-03-31T16:15:00Z", "payment-service", "auth_timeout_count", 342, "count"),
            ],
        },
        root_cause_service="auth-service",
        root_cause_keywords=["auth", "rs256", "rsa", "vault", "cache", "token", "validation", "deploy", "auth-v2.3.1"],
        required_remediation=["rollback_deploy"],
        optimal_action_sequence=["check_service_status", "query_logs:auth-service", "query_logs:checkout-service", "query_logs:payment-service", "query_logs:search-service", "check_metrics:auth-service", "identify_root_cause", "rollback_deploy:auth-service", "resolve_incident"],
        max_steps=25,
        red_herring_services=["search-service"],
    )


TASK_REGISTRY = {
    "easy_oom_kill": build_easy_task,
    "medium_connection_pool": build_medium_task,
    "hard_cascading_failure": build_hard_task,
}


def get_task(task_id: str) -> TaskScenario:
    builder = TASK_REGISTRY.get(task_id)
    if not builder:
        raise ValueError(f"Unknown task: {task_id}. Available: {list(TASK_REGISTRY.keys())}")
    return builder()
