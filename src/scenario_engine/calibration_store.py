"""CalibrationStore：持续记录预测与真实未来收益，用于周期性重校准。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STORE_DIR = Path("data") / "calibration"


class CalibrationStore:
    """按子指数与周期存储预测记录，支持预测与真实收益的异步写入。"""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_STORE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, sub_index: str, period: str) -> Path:
        return self.base_dir / f"{sub_index}_{period}_records.jsonl"

    def _load(self, sub_index: str, period: str) -> list[dict[str, Any]]:
        path = self._path(sub_index, period)
        if not path.exists():
            return []
        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def _save(
        self, sub_index: str, period: str, records: list[dict[str, Any]]
    ) -> None:
        path = self._path(sub_index, period)
        with path.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def record_prediction(
        self,
        sub_index: str,
        period: str,
        timestamp: str,
        scenario_key: str,
        probability: float,
    ) -> None:
        """记录一次情景概率预测。"""
        records = self._load(sub_index, period)
        records.append({
            "sub_index": sub_index,
            "period": period,
            "timestamp": timestamp,
            "scenario_key": scenario_key,
            "probability": float(probability),
        })
        self._save(sub_index, period, records)

    def record_outcome(
        self,
        sub_index: str,
        period: str,
        timestamp: str,
        scenario_key: str,
        future_return_5: float | None = None,
        future_return_7: float | None = None,
    ) -> None:
        """为已有预测记录补充真实未来收益。"""
        records = self._load(sub_index, period)
        for r in records:
            if r["timestamp"] == timestamp and r["scenario_key"] == scenario_key:
                if future_return_5 is not None:
                    r["future_return_5"] = float(future_return_5)
                if future_return_7 is not None:
                    r["future_return_7"] = float(future_return_7)
                break
        else:
            records.append({
                "sub_index": sub_index,
                "period": period,
                "timestamp": timestamp,
                "scenario_key": scenario_key,
                "future_return_5": float(future_return_5)
                if future_return_5 is not None
                else None,
                "future_return_7": float(future_return_7)
                if future_return_7 is not None
                else None,
            })
        self._save(sub_index, period, records)

    def load_records(self, sub_index: str, period: str) -> list[dict[str, Any]]:
        """加载指定子指数与周期的全部记录。"""
        return self._load(sub_index, period)
