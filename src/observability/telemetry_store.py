"""Zero-PII SQLite Telemetry Store for Scouts BSA Merit Badge Counselor Agent.

Persists strictly anonymous operational telemetry (badge popularity, warm vs.
cold bimodal latency histograms, per-stage pipeline latencies, image swap/regen
counts, and anonymous counselor star ratings) in SQLite.

Privacy & Security Guarantees:
- Explicitly rejects and strips any PII fields (`counselor_name`,
  `email_address`, `phone_number`, `troop_affiliation`, `location_or_zip`,
  `ip`, `client_ip`, `user_agent`, `custom_logo_data_uri`).
- Stores only aggregate / categorical operational metrics (`badge_name`,
  `audience_level`, `visual_style`, `duration_ms`, `cache_hit`, `stage_id`,
  `event_type`, `req_number`, `image_id`, `rating`).
"""

from __future__ import annotations

import logging
import math
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import LOCAL_SQLITE_DB_PATH

logger = logging.getLogger(__name__)

FORBIDDEN_PII_KEYS: frozenset[str] = frozenset({
    "counselor_name",
    "email_address",
    "phone_number",
    "troop_affiliation",
    "location_or_zip",
    "custom_logo_data_uri",
    "ip",
    "client_ip",
    "user_agent",
    "counselor_email",
    "counselor_phone",
    "counselor_location",
})


def scrub_pii_dict(payload: dict[str, Any] | None) -> dict[str, Any]:
  """Returns a shallow copy of payload with all forbidden PII keys removed."""
  if not isinstance(payload, dict):
    return {}
  return {
      k: v
      for k, v in payload.items()
      if str(k).strip().lower() not in FORBIDDEN_PII_KEYS
  }


def _percentile(sorted_vals: list[float], pct: float) -> float:
  """Calculates percentile on a pre-sorted list of floats."""
  if not sorted_vals:
    return 0.0
  idx = min(
      len(sorted_vals) - 1,
      max(0, math.ceil((pct / 100.0) * len(sorted_vals)) - 1),
  )
  return round(float(sorted_vals[idx]), 2)


class ZeroPiiTelemetryStore:
  """Thread-safe Zero-PII SQLite store for aggregate operational telemetry."""

  def __init__(self, db_path: str | None = None) -> None:
    resolved = db_path or os.environ.get(
        "LOCAL_SQLITE_DB_PATH", LOCAL_SQLITE_DB_PATH
    )
    self._db_path = str(Path(resolved).resolve())
    self._lock = threading.Lock()
    self._initialized = False
    self._ensure_schema()

  def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self._db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

  def _ensure_schema(self) -> None:
    if self._initialized:
      return
    with self._lock:
      if self._initialized:
        return
      try:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
          conn.execute("PRAGMA journal_mode=WAL;")
          conn.execute(
              """
              CREATE TABLE IF NOT EXISTS telemetry_workflow_runs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp_utc TEXT NOT NULL,
                  badge_name TEXT NOT NULL,
                  audience_level TEXT NOT NULL DEFAULT 'All Ages',
                  visual_style TEXT NOT NULL DEFAULT 'Norman Rockwell',
                  duration_ms REAL NOT NULL DEFAULT 0.0,
                  cache_hit INTEGER NOT NULL DEFAULT 0,
                  success INTEGER NOT NULL DEFAULT 1,
                  qa_score REAL NOT NULL DEFAULT 0.0,
                  estimated_cost_usd REAL NOT NULL DEFAULT 0.0
              )
              """
          )
          conn.execute(
              """
              CREATE TABLE IF NOT EXISTS telemetry_stage_latencies (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp_utc TEXT NOT NULL,
                  stage_id TEXT NOT NULL,
                  badge_name TEXT NOT NULL DEFAULT '',
                  duration_ms REAL NOT NULL DEFAULT 0.0,
                  cache_hit INTEGER NOT NULL DEFAULT 0
              )
              """
          )
          conn.execute(
              """
              CREATE TABLE IF NOT EXISTS telemetry_image_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp_utc TEXT NOT NULL,
                  badge_name TEXT NOT NULL,
                  req_number TEXT NOT NULL DEFAULT '',
                  event_type TEXT NOT NULL,
                  from_image_id TEXT NOT NULL DEFAULT '',
                  to_image_id TEXT NOT NULL DEFAULT ''
              )
              """
          )
          conn.execute(
              """
              CREATE TABLE IF NOT EXISTS telemetry_anonymous_feedback (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp_utc TEXT NOT NULL,
                  badge_name TEXT NOT NULL,
                  rating INTEGER NOT NULL,
                  promoted_to_golden INTEGER NOT NULL DEFAULT 0
              )
              """
          )
          conn.commit()
        self._initialized = True
      except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("ZeroPiiTelemetryStore schema init warning: %s", exc)

  def record_workflow_run(
      self,
      *,
      badge_name: str,
      duration_ms: float,
      cache_hit: bool = False,
      success: bool = True,
      audience_level: str = "All Ages",
      visual_style: str = "Norman Rockwell",
      qa_score: float = 0.0,
      estimated_cost_usd: float = 0.0,
      **extra_kwargs: Any,
  ) -> None:
    """Records a single workflow execution with zero PII."""
    _ = scrub_pii_dict(extra_kwargs)
    self._ensure_schema()
    now_iso = datetime.now(timezone.utc).isoformat()
    safe_badge = str(badge_name or "Unknown").strip()[:120]
    safe_audience = str(audience_level or "All Ages").strip()[:80]
    safe_style = str(visual_style or "Norman Rockwell").strip()[:80]
    try:
      with self._lock, self._connect() as conn:
        conn.execute(
            """
            INSERT INTO telemetry_workflow_runs (
                timestamp_utc, badge_name, audience_level, visual_style,
                duration_ms, cache_hit, success, qa_score, estimated_cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso,
                safe_badge,
                safe_audience,
                safe_style,
                max(0.0, float(duration_ms)),
                1 if cache_hit else 0,
                1 if success else 0,
                float(qa_score or 0.0),
                max(0.0, float(estimated_cost_usd or 0.0)),
            ),
        )
        conn.commit()
    except Exception as exc:  # pylint: disable=broad-exception-caught
      logger.debug("Telemetry record_workflow_run warning: %s", exc)

  def record_stage_latency(
      self,
      *,
      stage_id: str,
      duration_ms: float,
      badge_name: str = "",
      cache_hit: bool = False,
      **extra_kwargs: Any,
  ) -> None:
    """Records latency for one pipeline stage (`1`..`5` or named stage)."""
    _ = scrub_pii_dict(extra_kwargs)
    self._ensure_schema()
    now_iso = datetime.now(timezone.utc).isoformat()
    safe_stage = str(stage_id or "unknown").strip()[:64]
    safe_badge = str(badge_name or "").strip()[:120]
    try:
      with self._lock, self._connect() as conn:
        conn.execute(
            """
            INSERT INTO telemetry_stage_latencies (
                timestamp_utc, stage_id, badge_name, duration_ms, cache_hit
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                now_iso,
                safe_stage,
                safe_badge,
                max(0.0, float(duration_ms)),
                1 if cache_hit else 0,
            ),
        )
        conn.commit()
    except Exception as exc:  # pylint: disable=broad-exception-caught
      logger.debug("Telemetry record_stage_latency warning: %s", exc)

  def record_image_swap(
      self,
      *,
      badge_name: str,
      req_number: str = "",
      event_type: str = "swap",
      from_image_id: str = "",
      to_image_id: str = "",
      **extra_kwargs: Any,
  ) -> None:
    """Records an anonymous slide visual swap, regeneration, or promotion."""
    _ = scrub_pii_dict(extra_kwargs)
    self._ensure_schema()
    now_iso = datetime.now(timezone.utc).isoformat()
    safe_badge = str(badge_name or "Unknown").strip()[:120]
    safe_req = str(req_number or "").strip()[:32]
    safe_type = str(event_type or "swap").strip()[:48]
    safe_from = str(from_image_id or "").strip()[:160]
    safe_to = str(to_image_id or "").strip()[:160]
    try:
      with self._lock, self._connect() as conn:
        conn.execute(
            """
            INSERT INTO telemetry_image_events (
                timestamp_utc, badge_name, req_number, event_type,
                from_image_id, to_image_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (now_iso, safe_badge, safe_req, safe_type, safe_from, safe_to),
        )
        conn.commit()
    except Exception as exc:  # pylint: disable=broad-exception-caught
      logger.debug("Telemetry record_image_swap warning: %s", exc)

  def record_anonymous_feedback(
      self,
      *,
      badge_name: str,
      rating: int,
      promoted_to_golden: bool = False,
      **extra_kwargs: Any,
  ) -> None:
    """Records anonymous star rating without counselor identity."""
    _ = scrub_pii_dict(extra_kwargs)
    self._ensure_schema()
    now_iso = datetime.now(timezone.utc).isoformat()
    safe_badge = str(badge_name or "Unknown").strip()[:120]
    clamped_rating = max(1, min(5, int(rating)))
    try:
      with self._lock, self._connect() as conn:
        conn.execute(
            """
            INSERT INTO telemetry_anonymous_feedback (
                timestamp_utc, badge_name, rating, promoted_to_golden
            ) VALUES (?, ?, ?, ?)
            """,
            (
                now_iso,
                safe_badge,
                clamped_rating,
                1 if promoted_to_golden else 0,
            ),
        )
        conn.commit()
    except Exception as exc:  # pylint: disable=broad-exception-caught
      logger.debug("Telemetry record_anonymous_feedback warning: %s", exc)

  def get_telemetry_summary(self) -> dict[str, Any]:
    """Returns aggregated Zero-PII telemetry summary for the Admin Console."""
    self._ensure_schema()
    badge_popularity: list[dict[str, Any]] = []
    warm_latencies: list[float] = []
    cold_latencies: list[float] = []
    all_latencies: list[float] = []
    stage_breakdown: dict[str, dict[str, Any]] = {}
    image_swap_hotspot: list[dict[str, Any]] = []
    total_runs = 0
    cache_hits = 0
    success_runs = 0
    total_cost_usd = 0.0
    feedback_count = 0
    feedback_avg = 0.0
    golden_promotions = 0

    try:
      with self._lock, self._connect() as conn:
        # 1. Workflow runs summary & bimodal latencies
        cur = conn.execute(
            """
            SELECT duration_ms, cache_hit, success, estimated_cost_usd
            FROM telemetry_workflow_runs
            ORDER BY id DESC
            LIMIT 5000
            """
        )
        for row in cur.fetchall():
          total_runs += 1
          dur = float(row["duration_ms"] or 0.0)
          is_hit = bool(row["cache_hit"])
          is_ok = bool(row["success"])
          total_cost_usd += float(row["estimated_cost_usd"] or 0.0)
          all_latencies.append(dur)
          if is_hit:
            cache_hits += 1
            warm_latencies.append(dur)
          else:
            cold_latencies.append(dur)
          if is_ok:
            success_runs += 1

        # 2. Top badges popularity
        cur_badges = conn.execute(
            """
            SELECT
                badge_name,
                COUNT(*) AS run_count,
                SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) AS warm_runs,
                SUM(CASE WHEN cache_hit = 0 THEN 1 ELSE 0 END) AS cold_runs,
                AVG(duration_ms) AS avg_duration_ms,
                AVG(qa_score) AS avg_qa_score
            FROM telemetry_workflow_runs
            GROUP BY badge_name
            ORDER BY run_count DESC, badge_name ASC
            LIMIT 25
            """
        )
        for row in cur_badges.fetchall():
          badge_popularity.append({
              "badge_name": row["badge_name"],
              "run_count": int(row["run_count"] or 0),
              "warm_runs": int(row["warm_runs"] or 0),
              "cold_runs": int(row["cold_runs"] or 0),
              "avg_duration_ms": round(float(row["avg_duration_ms"] or 0.0), 1),
              "avg_qa_score": round(float(row["avg_qa_score"] or 0.0), 1),
          })

        # 3. Stage latencies breakdown
        cur_stages = conn.execute(
            """
            SELECT stage_id, duration_ms
            FROM telemetry_stage_latencies
            ORDER BY id DESC
            LIMIT 5000
            """
        )
        stage_samples: dict[str, list[float]] = {}
        for row in cur_stages.fetchall():
          sid = str(row["stage_id"])
          stage_samples.setdefault(sid, []).append(float(row["duration_ms"] or 0.0))

        for sid, vals in sorted(stage_samples.items()):
          s_vals = sorted(vals)
          stage_breakdown[sid] = {
              "sample_count": len(s_vals),
              "p50_ms": _percentile(s_vals, 50),
              "p95_ms": _percentile(s_vals, 95),
              "avg_ms": round(sum(s_vals) / len(s_vals), 2) if s_vals else 0.0,
          }

        # 4. Image swap / regeneration hotspots
        cur_swaps = conn.execute(
            """
            SELECT
                badge_name,
                req_number,
                event_type,
                COUNT(*) AS event_count
            FROM telemetry_image_events
            GROUP BY badge_name, req_number, event_type
            ORDER BY event_count DESC
            LIMIT 25
            """
        )
        for row in cur_swaps.fetchall():
          image_swap_hotspot.append({
              "badge_name": row["badge_name"],
              "req_number": row["req_number"] or "All",
              "event_type": row["event_type"],
              "event_count": int(row["event_count"] or 0),
          })

        # 5. Anonymous feedback summary
        cur_fb = conn.execute(
            """
            SELECT
                COUNT(*) AS cnt,
                AVG(rating) AS avg_rating,
                SUM(promoted_to_golden) AS golden_cnt
            FROM telemetry_anonymous_feedback
            """
        )
        fb_row = cur_fb.fetchone()
        if fb_row and fb_row["cnt"]:
          feedback_count = int(fb_row["cnt"] or 0)
          feedback_avg = round(float(fb_row["avg_rating"] or 0.0), 2)
          golden_promotions = int(fb_row["golden_cnt"] or 0)
    except Exception as exc:  # pylint: disable=broad-exception-caught
      logger.debug("Telemetry get_telemetry_summary warning: %s", exc)

    s_all = sorted(all_latencies)
    s_warm = sorted(warm_latencies)
    s_cold = sorted(cold_latencies)

    return {
        "zero_pii_enforced": True,
        "forbidden_pii_fields": sorted(FORBIDDEN_PII_KEYS),
        "total_runs": total_runs,
        "cache_hits": cache_hits,
        "cache_misses": max(0, total_runs - cache_hits),
        "cache_hit_ratio": (
            round(cache_hits / total_runs, 4) if total_runs > 0 else 0.0
        ),
        "success_rate": (
            round(success_runs / total_runs, 4) if total_runs > 0 else 1.0
        ),
        "total_estimated_cost_usd": round(total_cost_usd, 4),
        "latency_overall_ms": {
            "count": len(s_all),
            "p50": _percentile(s_all, 50),
            "p95": _percentile(s_all, 95),
            "p99": _percentile(s_all, 99),
        },
        "latency_warm_ms": {
            "count": len(s_warm),
            "p50": _percentile(s_warm, 50),
            "p95": _percentile(s_warm, 95),
            "p99": _percentile(s_warm, 99),
        },
        "latency_cold_ms": {
            "count": len(s_cold),
            "p50": _percentile(s_cold, 50),
            "p95": _percentile(s_cold, 95),
            "p99": _percentile(s_cold, 99),
        },
        "stage_latencies_ms": stage_breakdown,
        "badge_popularity": badge_popularity,
        "image_swap_hotspots": image_swap_hotspot,
        "anonymous_feedback": {
            "total_ratings": feedback_count,
            "average_rating": feedback_avg,
            "golden_promotions": golden_promotions,
        },
    }


_DEFAULT_TELEMETRY_STORE: ZeroPiiTelemetryStore | None = None
_STORE_INIT_LOCK = threading.Lock()


def get_zero_pii_telemetry_store() -> ZeroPiiTelemetryStore:
  """Returns the singleton ZeroPiiTelemetryStore instance."""
  global _DEFAULT_TELEMETRY_STORE
  if _DEFAULT_TELEMETRY_STORE is None:
    with _STORE_INIT_LOCK:
      if _DEFAULT_TELEMETRY_STORE is None:
        _DEFAULT_TELEMETRY_STORE = ZeroPiiTelemetryStore()
  return _DEFAULT_TELEMETRY_STORE
