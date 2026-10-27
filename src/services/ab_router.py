"""Deterministic SHA-256 Online A/B Experiment Traffic Router (`src/services/ab_router.py`).

Routes counselor sessions deterministically between `control` (`gemini-2.5-flash-standard`)
and `treatment` (`gemini-2.5-flash-grounded-cot`) using SHA-256 modulo-100 bucketing
and records per-variant latency and quality outcomes for BigQuery scorecard analysis.
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Dict, List


class ABExperimentRouter:
    """Thread-safe deterministic A/B router for prompt and model variant experiments."""

    DEFAULT_EXPERIMENT_ID = "curriculum_synthesis_v2"
    CONTROL_MODEL = "gemini-2.5-flash-standard"
    TREATMENT_MODEL = "gemini-2.5-flash-grounded-cot"

    def __init__(self, treatment_split_pct: int = 50) -> None:
        self.treatment_split_pct = max(0, min(100, int(treatment_split_pct)))
        self._lock = threading.Lock()
        self._outcomes: Dict[str, List[Dict[str, float]]] = {
            "control": [],
            "treatment": [],
        }
        self._assignments: Dict[str, int] = {
            "control": 0,
            "treatment": 0,
        }

    @staticmethod
    def compute_bucket(session_id: str, experiment_id: str = DEFAULT_EXPERIMENT_ID) -> int:
        """Computes a deterministic 0..99 bucket index from `experiment_id:session_id`."""
        clean_session = str(session_id or "default_session").strip()
        clean_exp = str(experiment_id or ABExperimentRouter.DEFAULT_EXPERIMENT_ID).strip()
        key = f"{clean_exp}:{clean_session}"
        return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100

    def assign_variant(
        self,
        session_id: str,
        experiment_id: str = DEFAULT_EXPERIMENT_ID,
    ) -> Dict[str, Any]:
        """Deterministically assigns `session_id` to `control` or `treatment`."""
        bucket = self.compute_bucket(session_id=session_id, experiment_id=experiment_id)
        is_treatment = bucket < self.treatment_split_pct
        variant = "treatment" if is_treatment else "control"
        model_variant = self.TREATMENT_MODEL if is_treatment else self.CONTROL_MODEL
        prompt_strategy = (
            "grounded_chain_of_thought_v2" if is_treatment else "standard_curriculum_v1"
        )

        with self._lock:
            self._assignments[variant] = self._assignments.get(variant, 0) + 1

        return {
            "experiment_id": str(experiment_id or self.DEFAULT_EXPERIMENT_ID),
            "session_id": str(session_id or "default_session"),
            "bucket": bucket,
            "variant": variant,
            "model_variant": model_variant,
            "prompt_strategy": prompt_strategy,
            "treatment_split_pct": self.treatment_split_pct,
        }

    def record_outcome(
        self,
        variant: str,
        latency_ms: float,
        quality_score: float = 1.0,
    ) -> Dict[str, Any]:
        """Records latency and quality outcome metrics for a routed session variant."""
        norm_variant = "treatment" if str(variant).strip().lower() == "treatment" else "control"
        clean_lat = max(0.0, float(latency_ms))
        clean_qual = max(0.0, min(5.0, float(quality_score)))
        entry = {
            "latency_ms": round(clean_lat, 2),
            "quality_score": round(clean_qual, 4),
            "recorded_at_epoch": round(time.time(), 3),
        }
        with self._lock:
            bucket_list = self._outcomes.setdefault(norm_variant, [])
            bucket_list.append(entry)
            if len(bucket_list) > 1000:
                del bucket_list[:-1000]
            count = len(bucket_list)
        return {
            "status": "RECORDED",
            "variant": norm_variant,
            "sample_count": count,
            **entry,
        }

    def get_experiment_summary(self) -> Dict[str, Any]:
        """Returns aggregate A/B assignment counts, average latency, and quality scores."""
        with self._lock:
            assignments_copy = dict(self._assignments)
            outcomes_copy = {k: list(v) for k, v in self._outcomes.items()}

        variants_summary: Dict[str, Dict[str, Any]] = {}
        for var_name, model_id in (
            ("control", self.CONTROL_MODEL),
            ("treatment", self.TREATMENT_MODEL),
        ):
            rows = outcomes_copy.get(var_name, [])
            avg_lat = (
                round(sum(r["latency_ms"] for r in rows) / len(rows), 2) if rows else 0.0
            )
            avg_qual = (
                round(sum(r["quality_score"] for r in rows) / len(rows), 4) if rows else 1.0
            )
            variants_summary[var_name] = {
                "model_variant": model_id,
                "assigned_sessions": assignments_copy.get(var_name, 0),
                "recorded_outcomes": len(rows),
                "avg_latency_ms": avg_lat,
                "avg_quality_score": avg_qual,
            }

        return {
            "experiment_id": self.DEFAULT_EXPERIMENT_ID,
            "treatment_split_pct": self.treatment_split_pct,
            "hash_algorithm": "sha256_mod_100",
            "variants": variants_summary,
        }


ABTrafficRouter = ABExperimentRouter
GLOBAL_AB_ROUTER = ABExperimentRouter()
