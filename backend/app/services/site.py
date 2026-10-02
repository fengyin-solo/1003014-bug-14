"""基站台账业务规则：字段校验、筛选口径、状态流转与操作轨迹。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "site"
REQUIRED_FIELDS = ["基站编号", "基站名称", "基站类型"]
OPTIONAL_FIELDS = ["所属区县", "经纬度坐标", "铁塔高度", "入网日期"]
ENTRY_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
STATUS_FIELD = "基站状态"
STATUS_ORDER = ["运行中", "退服中", "已退网", "已拆除"]
FORWARD_ACTIONS = {
    "登记退服": (STATUS_ORDER[0], STATUS_ORDER[1]),
    "申请退网": (STATUS_ORDER[1], STATUS_ORDER[2]),
    "拆站完成": (STATUS_ORDER[2], STATUS_ORDER[3]),
}
RECOVERY_ACTIONS = {"恢复", "恢复运行"}
HISTORY_FIELD = "操作轨迹"


class SiteService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._display_row(dict(row)) for row in store.rows(MODULE)]
        keyword = (keyword or "").strip()
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("基站编号", ""))]
        if status:
            rows = [row for row in rows if row.get(STATUS_FIELD) == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._display_row(dict(entry))

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        normalized = self._normalize_values(values)
        missing = [field for field in REQUIRED_FIELDS if not normalized.get(field)]
        if missing:
            return None, missing

        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ENTRY_FIELDS:
            entry[field] = normalized.get(field)
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_FIELD] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry[HISTORY_FIELD] = [{
            "action": "登记入网",
            "from": None,
            "to": STATUS_ORDER[0],
            "time": self._now(),
        }]
        rows.append(entry)
        return self._display_row(dict(entry)), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"基站 {entry_id} 不存在或已归档"

        action = action.strip()
        current = str(entry.get("status"))
        if current not in STATUS_ORDER:
            return None, f"当前状态「{current}」不在允许的状态序列里"

        if action in FORWARD_ACTIONS:
            expected, target = FORWARD_ACTIONS[action]
            if current != expected:
                if STATUS_ORDER.index(current) > STATUS_ORDER.index(expected):
                    return None, f"当前状态为{current}，不能倒回执行「{action}」；如需回退请先执行「恢复」"
                return None, f"基站当前为{current}，需先完成前一状态动作，不能直接{action}"
        elif action in RECOVERY_ACTIONS:
            if current == STATUS_ORDER[0]:
                return None, "运行中的基站不需要恢复"
            if current == STATUS_ORDER[-1]:
                return None, "已拆除基站不能恢复，请通过新建台账重新登记"
            target = STATUS_ORDER[0]
        else:
            return None, f"动作「{action}」不属于基站台账可执行范围"

        entry["status"] = target
        entry[STATUS_FIELD] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry.setdefault(HISTORY_FIELD, []).append({
            "action": action,
            "from": current,
            "to": target,
            "time": self._now(),
        })
        return self._display_row(dict(entry)), f"基站已{action}"

    def _normalize_values(self, values: dict[str, Any]) -> dict[str, str | None]:
        normalized: dict[str, str | None] = {}
        for field in ENTRY_FIELDS:
            value = values.get(field)
            if value is None:
                normalized[field] = None
            else:
                text = str(value).strip()
                normalized[field] = text or None
        return normalized

    def _display_row(self, row: dict[str, Any]) -> dict[str, Any]:
        status = str(row.get("status") or row.get(STATUS_FIELD) or STATUS_ORDER[0])
        row["status"] = status
        row[STATUS_FIELD] = status
        row.setdefault(HISTORY_FIELD, [])
        return row

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
