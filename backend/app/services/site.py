"""基站台账业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "site"
LEDGER_FIELDS = ["基站编号", "基站名称", "基站类型", "所属区县", "经纬度坐标", "铁塔高度", "入网日期", "基站状态"]
REQUIRED_FIELDS = ["基站编号", "基站名称", "基站类型"]
STATUS_FIELD = "基站状态"
STATUS_ORDER = ["运行中", "退服中", "已退网", "已拆除"]
ACTION_RULES = {"登记退服": "退服中", "申请退网": "已退网", "拆站完成": "已拆除"}
RESTORE_ACTION = "恢复"
NEGATIVE_ACTIONS: list[str] = []


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class SiteService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        station_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("基站编号", ""))]
        if name:
            rows = [row for row in rows if name in str(row.get("基站名称", ""))]
        if station_type:
            rows = [row for row in rows if station_type in str(row.get("基站类型", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in LEDGER_FIELDS:
            if field == STATUS_FIELD:
                continue
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_FIELD] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["流转记录"] = [{"动作": "登记基站", "从": "", "到": STATUS_ORDER[0], "时间": _now()}]
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"基站 {entry_id} 不存在或已归档"
        current = str(entry.get("status") or "")
        if current not in STATUS_ORDER:
            return None, f"基站当前状态「{current}」不在允许的状态序列里，请先修正台账"
        if action == RESTORE_ACTION:
            index = STATUS_ORDER.index(current)
            if index == 0:
                return None, f"基站已处于「{STATUS_ORDER[0]}」，没有可恢复的上一步"
            target = STATUS_ORDER[index - 1]
        elif action in ACTION_RULES:
            target = ACTION_RULES[action]
            if STATUS_ORDER.index(current) + 1 != STATUS_ORDER.index(target):
                path = "→".join(STATUS_ORDER)
                return None, f"当前状态为「{current}」，只能按 {path} 逐级前行；如需回退请执行「{RESTORE_ACTION}」"
        else:
            return None, f"动作「{action}」不属于基站台账可执行范围"
        entry["status"] = target
        entry[STATUS_FIELD] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        entry.setdefault("流转记录", []).append({"动作": action, "从": current, "到": target, "时间": _now()})
        return entry, f"基站已{action}，当前状态「{target}」"
