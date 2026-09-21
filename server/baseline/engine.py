from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any, Dict, Optional

from server.storage.base import BaseStorage


@dataclass
class UserBaseline:
    username: str
    feature_means: Dict[str, float] = field(default_factory=dict)
    feature_stds: Dict[str, float] = field(default_factory=dict)
    sample_count: int = 0
    hour_profiles: Dict[int, Dict[str, float]] = field(default_factory=dict)
    last_updated: str = ""
    decay_factor: float = 0.05
    
    # Independent Missingness Tracking
    feature_missing_counts: Dict[str, int] = field(default_factory=dict)
    feature_sample_counts: Dict[str, int] = field(default_factory=dict)
    
    # 1-Day Short Term Buffer
    short_term_sums: Dict[str, float] = field(default_factory=dict)
    short_term_counts: Dict[str, int] = field(default_factory=dict)
    last_merge_date: str = ""

    @property
    def confidence_score(self) -> float:
        return min(self.sample_count / 14.0, 1.0) if self.sample_count > 0 else 0.1


class BaselineEngine:
    def __init__(self, storage: BaseStorage, window_days: int = 30) -> None:
        self.storage = storage
        self.window_days = window_days
        # EMA Equivalent for N days: 2 / (N + 1)
        self.decay = 2.0 / (window_days + 1.0)

    def _get_role_for_user(self, user: str) -> str:
        lower = user.lower()
        if "admin" in lower or "sys" in lower or "root" in lower:
            return "administrator"
        return "standard_user"

    def get_baseline(self, user: str) -> Optional[UserBaseline]:
        row = self.storage.load_baseline(user)
        if not row:
            return None
        metadata = row.get("metadata_json") or {}
        return UserBaseline(
            username=row.get("username") or user,
            feature_means=dict(metadata.get("feature_means") or {}),
            feature_stds=dict(metadata.get("feature_stds") or {}),
            sample_count=int(row.get("sample_count") or 0),
            hour_profiles=dict(metadata.get("hour_profiles") or {}),
            last_updated=row.get("created_at") or "",
            decay_factor=float(metadata.get("decay_factor") or self.decay),
            feature_missing_counts=dict(metadata.get("feature_missing_counts") or {}),
            feature_sample_counts=dict(metadata.get("feature_sample_counts") or {}),
            short_term_sums=dict(metadata.get("short_term_sums") or {}),
            short_term_counts=dict(metadata.get("short_term_counts") or {}),
            last_merge_date=metadata.get("last_merge_date") or ""
        )

    def _update_single_baseline(self, entity_id: str, features: Dict[str, float]) -> dict[str, Any]:
        current = self.get_baseline(entity_id) or UserBaseline(username=entity_id, decay_factor=self.decay)
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Merge short term buffer into long term EMA if a day has passed
        if current.last_merge_date and current.last_merge_date != today_date:
            for feature, count in current.short_term_counts.items():
                if count > 0:
                    daily_avg = current.short_term_sums.get(feature, 0.0) / count
                    
                    prev_mean = current.feature_means.get(feature, daily_avg)
                    updated_mean = (1 - self.decay) * prev_mean + self.decay * daily_avg
                    current.feature_means[feature] = updated_mean
                    
                    prev_std = current.feature_stds.get(feature, 10.0)
                    updated_std = (1 - self.decay) * prev_std + self.decay * abs(daily_avg - updated_mean)
                    current.feature_stds[feature] = max(updated_std, abs(updated_mean) * 0.25, 10.0)
            
            # Reset buffer
            current.short_term_sums = {}
            current.short_term_counts = {}
            
        current.last_merge_date = today_date
        current.sample_count += 1
        
        # Add current features to short term buffer
        all_known_features = set(current.feature_means.keys()).union(features.keys())
        for feature_name in all_known_features:
            if feature_name in features:
                value = features[feature_name]
                current.short_term_sums[feature_name] = current.short_term_sums.get(feature_name, 0.0) + value
                current.short_term_counts[feature_name] = current.short_term_counts.get(feature_name, 0) + 1
                current.feature_sample_counts[feature_name] = current.feature_sample_counts.get(feature_name, 0) + 1
            else:
                current.feature_missing_counts[feature_name] = current.feature_missing_counts.get(feature_name, 0) + 1

        payload = {
            "agent_id": None,
            "username": entity_id,
            "feature_name": "__aggregate__",
            "baseline_scope": "user",
            "window_start": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "window_end": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mean_value": 0.0,
            "std_value": 0.0,
            "sample_count": current.sample_count,
            "logic_version": "2.0",
            "metadata_json": {
                "feature_means": current.feature_means,
                "feature_stds": current.feature_stds,
                "feature_missing_counts": current.feature_missing_counts,
                "feature_sample_counts": current.feature_sample_counts,
                "short_term_sums": current.short_term_sums,
                "short_term_counts": current.short_term_counts,
                "last_merge_date": current.last_merge_date,
                "hour_profiles": current.hour_profiles,
                "decay_factor": self.decay,
            },
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self.storage.save_baseline(payload)
        return payload

    def update_baseline(self, user: str, features: Dict[str, float], hour: int):
        user_payload = self._update_single_baseline(user, features)
        role = self._get_role_for_user(user)
        self._update_single_baseline(f"__role_{role}__", features)
        return user_payload

    def get_deviation_vector(self, user: str, features: Dict[str, float]) -> Dict[str, float]:
        baseline = self.get_baseline(user)
        role = self._get_role_for_user(user)
        role_baseline = self.get_baseline(f"__role_{role}__")

        deviations: Dict[str, float] = {}
        for name, value in features.items():
            if baseline and baseline.feature_sample_counts.get(name, 0) >= 5:
                mean_value = baseline.feature_means.get(name, value)
                std_value = baseline.feature_stds.get(name, 1.0) or 1.0
            elif role_baseline and role_baseline.feature_sample_counts.get(name, 0) > 0:
                mean_value = role_baseline.feature_means.get(name, value)
                std_value = role_baseline.feature_stds.get(name, 1.0) or 1.0
            else:
                mean_value = value
                std_value = 1.0

            deviations[name] = (value - mean_value) / std_value
        return deviations

    def get_rolling_window(self, user: str, days: int = 7) -> Dict[str, Any]:
        baseline = self.get_baseline(user)
        if baseline is None:
            return {"user": user, "days": days, "samples": []}
        return {
            "user": user,
            "days": days,
            "samples": [
                {
                    "feature": feature,
                    "mean": baseline.feature_means.get(feature, 0.0),
                    "std": baseline.feature_stds.get(feature, 0.0),
                    "samples": baseline.feature_sample_counts.get(feature, 0),
                    "missing": baseline.feature_missing_counts.get(feature, 0),
                }
                for feature in sorted(baseline.feature_means)
            ],
        }
