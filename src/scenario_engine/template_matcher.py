"""预定义模式模板匹配引擎。

输入 OHLC DataFrame，根据 ``config/scenario_templates/*.json`` 中定义的
结构条件、价格条件、时间条件与推演规则，输出匹配到的经典价格形态列表。
"""

from __future__ import annotations

import ast
import json
import operator
from pathlib import Path
from typing import Any

import pandas as pd

from src.features.swing import identify_swing_points
from src.features.trend_strength import add_trend_strength_features


DEFAULT_TEMPLATES_DIR = Path(__file__).parents[2] / "config" / "scenario_templates"

# 全局模板缓存：默认模板目录在运行期间不变，避免每次从磁盘重新加载。
_TEMPLATE_CACHE: dict[str | Path, list[dict]] = {}


class TemplateError(ValueError):
    """模板解析或执行错误。"""


def load_templates(templates: str | Path | list[dict] | None = None) -> list[dict]:
    """加载一个或多个模板。

    默认目录会被缓存；显式传入的已解析列表或文件路径不会被缓存。

    Args:
        templates: 模板目录、模板 JSON 文件、已解析的模板列表，或 ``None``
            表示加载默认目录 ``config/scenario_templates`` 下的全部模板。

    Returns:
        模板对象列表。
    """
    if templates is None:
        key = str(DEFAULT_TEMPLATES_DIR)
        if key not in _TEMPLATE_CACHE:
            _TEMPLATE_CACHE[key] = _load_template_dir(DEFAULT_TEMPLATES_DIR)
        return list(_TEMPLATE_CACHE[key])

    if isinstance(templates, list):
        return list(templates)

    path = Path(templates)
    if path.is_dir():
        return _load_template_dir(path)

    return _load_template_file(path)


def _load_template_dir(directory: Path) -> list[dict]:
    loaded: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        loaded.extend(_load_template_file(path))
    return _deduplicate_template_names(loaded)


def _load_template_file(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise TemplateError(f"Template file must contain an object or array: {path}")


def _deduplicate_template_names(templates: list[dict]) -> list[dict]:
    seen: set[str] = set()
    for template in templates:
        name = template.get("name")
        if name in seen:
            raise TemplateError(f"Duplicate template name: {name}")
        seen.add(name)
    return templates


def _ensure_ohlc(df: pd.DataFrame) -> None:
    missing = {"open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise ValueError(f"df must contain open, high, low, close columns; missing {missing}")


def _prepare_features(df: pd.DataFrame, swing_order: int) -> pd.DataFrame:
    """确保 DataFrame 包含 swing_high、swing_low 与 atr 列。"""
    result = identify_swing_points(df, high_col="high", low_col="low", order=swing_order)
    result = add_trend_strength_features(result)
    result["atr"] = result["atr"].fillna(0.0)
    return result


def _build_event_list(df: pd.DataFrame) -> list[dict[str, Any]]:
    """将 swing_high / swing_low 转换为按时间排序的事件列表。"""
    events: list[dict[str, Any]] = []
    for i in range(len(df)):
        row = df.iloc[i]
        if row["swing_high"]:
            events.append({"idx": i, "type": "high", "price": float(row["high"])})
        if row["swing_low"]:
            events.append({"idx": i, "type": "low", "price": float(row["low"])})
    return events


def _append_synthetic_events(
    events: list[dict[str, Any]],
    df: pd.DataFrame,
    current_index: int,
) -> list[dict[str, Any]]:
    """将当前 K 线以 ``high`` / ``low`` 两种身份追加到事件列表。

    这使得以当前收盘价完成突破的模板（如多头三浪延伸）能够把最后一
    个 Swing 点视为当前 K 线，而不受后续 K 线创出更高点的影响。
    """
    close = float(df["close"].iloc[current_index])
    return events + [
        {"idx": current_index, "type": "high", "price": close},
        {"idx": current_index, "type": "low", "price": close},
    ]


def _find_last_matching_subsequence(
    events: list[dict[str, Any]],
    sequence: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """返回与 ``sequence`` 类型顺序匹配的、时间最晚的事件子序列。"""
    matched: list[dict[str, Any]] = []
    ev_idx = len(events) - 1
    for point in reversed(sequence):
        expected = point["type"]
        while ev_idx >= 0 and events[ev_idx]["type"] != expected:
            ev_idx -= 1
        if ev_idx < 0:
            return None
        matched.append(events[ev_idx])
        ev_idx -= 1
    matched.reverse()
    # 确保时间单调递增
    if any(matched[i]["idx"] >= matched[i + 1]["idx"] for i in range(len(matched) - 1)):
        return None
    return matched


def _safe_eval(expr: str, ctx: dict[str, float]) -> float:
    """安全地计算公式表达式。

    允许的节点：常量、变量、加减乘除、以及 ``min`` / ``max`` / ``abs`` 调用。
    """
    tree = ast.parse(expr, mode="eval")

    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Call,
        ast.Name,
        ast.Constant,
        ast.Load,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.USub,
        ast.UAdd,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise TemplateError(f"Disallowed syntax in formula: {expr!r}")

    def _eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in ctx:
                raise TemplateError(f"Unknown variable {node.id!r} in formula {expr!r}")
            return float(ctx[node.id])
        if isinstance(node, ast.BinOp):
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    return float("inf")
                return left / right
        if isinstance(node, ast.UnaryOp):
            operand = _eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in {"min", "max", "abs"}:
                raise TemplateError(f"Disallowed function call in formula: {expr!r}")
            args = [_eval_node(arg) for arg in node.args]
            builtin = __builtins__.get(node.func.id) if isinstance(__builtins__, dict) else getattr(__builtins__, node.func.id)
            return builtin(*args)
        raise TemplateError(f"Unsupported node in formula: {expr!r}")

    return _eval_node(tree.body)


def _resolve_value(value: str | float | int, ctx: dict[str, float]) -> float:
    """将模板操作数解析为数值。

    数值常量直接返回；字符串如果是已注册变量名直接返回变量值；
    否则作为公式表达式求值。
    """
    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        raise TemplateError(f"Unsupported operand type: {value!r}")

    if value in ctx:
        return float(ctx[value])

    try:
        return float(value)
    except ValueError:
        return _safe_eval(value, ctx)


def _build_context(
    events: list[dict[str, Any]],
    sequence: list[dict[str, Any]],
    df: pd.DataFrame,
    current_index: int,
    direction_hint: str,
) -> dict[str, float] | None:
    """为当前候选序列构造求值上下文。

    上下文中包含每个 Swing 标签的价格与下标、当前 close / atr / prev_close，
    以及 ``direction``（+1 看多、-1 看空、0 中性）。
    """
    if len(events) != len(sequence):
        return None

    ctx: dict[str, float] = {
        "close": float(df["close"].iloc[current_index]),
        "atr": float(df["atr"].iloc[current_index]),
        "direction": {"bullish": 1.0, "bearish": -1.0, "both": 0.0}.get(direction_hint, 0.0),
    }
    if current_index > 0:
        ctx["prev_close"] = float(df["close"].iloc[current_index - 1])
    else:
        ctx["prev_close"] = ctx["close"]

    for event, point in zip(events, sequence):
        expected = point["type"]
        if event["type"] != expected:
            return None
        label = point["label"]
        ctx[label] = event["price"]
        ctx[f"{label}_idx"] = float(event["idx"])

    return ctx


def _evaluate_structural_condition(cond: dict[str, Any], ctx: dict[str, float]) -> tuple[bool, float]:
    ctype = cond["type"]
    if ctype in {"swing_high", "swing_low"}:
        label = cond.get("label")
        return label in ctx, 1.0

    left = _resolve_value(cond["left"], ctx)
    right = _resolve_value(cond["right"], ctx)

    ops = {
        "higher_high": operator.gt,
        "higher_low": operator.gt,
        "lower_high": operator.lt,
        "lower_low": operator.lt,
    }
    op = ops.get(ctype)
    if op is None:
        raise TemplateError(f"Unknown structural condition type: {ctype}")

    ok = op(right, left)
    return ok, 1.0 if ok else 0.0


def _evaluate_price_condition(cond: dict[str, Any], ctx: dict[str, float]) -> tuple[bool, float]:
    ctype = cond["type"]

    if ctype == "price_ratio":
        left = _resolve_value(cond["left"], ctx)
        right = _resolve_value(cond["right"], ctx)
        base = _resolve_value(cond.get("base", 1.0), ctx)
        if base == 0:
            return False, 0.0
        ratio = abs(left - right) / abs(base)
        min_ratio = cond.get("min_ratio")
        max_ratio = cond.get("max_ratio")
        ok = True
        if min_ratio is not None and ratio < min_ratio:
            ok = False
        if max_ratio is not None and ratio > max_ratio:
            ok = False
        if ok:
            return True, 1.0
        # 部分得分：越界越多得分越低
        if max_ratio is not None and ratio > max_ratio:
            partial = max(0.0, 1.0 - (ratio - max_ratio) / max_ratio)
        elif min_ratio is not None and ratio < min_ratio:
            partial = max(0.0, 1.0 - (min_ratio - ratio) / min_ratio)
        else:
            partial = 0.0
        return False, partial

    if ctype == "atr_multiple":
        a = _resolve_value(cond["a"], ctx)
        b = _resolve_value(cond["b"], ctx)
        atr = ctx.get("atr", 0.0)
        if atr <= 0:
            return False, 0.0
        value = abs(a - b) / atr
        min_m = cond.get("min_multiple")
        max_m = cond.get("max_multiple")
        ok = True
        if min_m is not None and value < min_m:
            ok = False
        if max_m is not None and value > max_m:
            ok = False
        if ok:
            return True, 1.0
        if max_m is not None and value > max_m:
            partial = max(0.0, 1.0 - (value - max_m) / max_m)
        elif min_m is not None and value < min_m:
            partial = max(0.0, 1.0 - (min_m - value) / min_m)
        else:
            partial = 0.0
        return False, partial

    if ctype == "fib_retracement":
        start = _resolve_value(cond["swing_start"], ctx)
        end = _resolve_value(cond["swing_end"], ctx)
        point = _resolve_value(cond["point"], ctx)
        swing_range = abs(end - start)
        if swing_range == 0:
            return False, 0.0
        ratio = abs(point - end) / swing_range
        levels = [float(lvl) for lvl in cond.get("levels", [])]
        tolerance = cond.get("tolerance", 0.05)
        if not levels:
            return False, 0.0
        distances = [abs(ratio - lvl) for lvl in levels]
        best = min(distances)
        ok = best <= tolerance
        partial = max(0.0, 1.0 - best / tolerance) if tolerance > 0 else (1.0 if ok else 0.0)
        return ok, partial

    if ctype == "breakout":
        level = _resolve_value(cond["level"], ctx)
        close = ctx["close"]
        prev_close = ctx.get("prev_close", close)
        direction = cond.get("direction", "bullish")
        require_cross = cond.get("require_cross", False)
        if direction == "bullish":
            ok = close > level
            if require_cross:
                ok = ok and prev_close <= level
        else:
            ok = close < level
            if require_cross:
                ok = ok and prev_close >= level
        return ok, 1.0 if ok else 0.0

    raise TemplateError(f"Unknown price condition type: {ctype}")


def _evaluate_time_condition(cond: dict[str, Any], ctx: dict[str, float]) -> tuple[bool, float]:
    ctype = cond["type"]
    value = cond["value"]

    start_label = cond.get("start")
    end_label = cond.get("end")

    if ctype in {"min_bars", "max_bars"}:
        start_idx = int(ctx[f"{start_label}_idx"])
        end_idx = int(ctx[f"{end_label}_idx"])
        bars = end_idx - start_idx
        if ctype == "min_bars":
            return bars >= value, 1.0 if bars >= value else max(0.0, bars / value)
        return bars <= value, 1.0 if bars <= value else max(0.0, value / bars)

    if ctype == "max_gap":
        if start_label is not None and end_label is not None:
            indices = [int(ctx[f"{start_label}_idx"]), int(ctx[f"{end_label}_idx"])]
        else:
            indices = sorted(
                int(ctx[k]) for k in ctx if k.endswith("_idx") and not k.startswith("__")
            )
        gaps = [indices[i + 1] - indices[i] for i in range(len(indices) - 1)]
        if not gaps:
            return True, 1.0
        max_gap = max(gaps)
        return max_gap <= value, 1.0 if max_gap <= value else max(0.0, value / max_gap)

    raise TemplateError(f"Unknown time condition type: {ctype}")


def _evaluate_conditions(
    template: dict[str, Any],
    ctx: dict[str, float],
) -> tuple[bool, float, dict[str, Any]]:
    """评估模板全部条件。

    Returns:
        (all_required_passed, confidence, details)
    """
    structure = template.get("structure", {})
    groups = [
        ("structural", structure.get("structural_conditions", [])),
        ("price", structure.get("price_conditions", [])),
        ("time", structure.get("time_conditions", [])),
    ]

    total_score = 0.0
    total_count = 0
    details: dict[str, Any] = {}
    all_required_passed = True

    for group_name, conditions in groups:
        group_details: list[dict[str, Any]] = []
        for cond in conditions:
            required = cond.get("required", True)
            if group_name == "structural":
                ok, score = _evaluate_structural_condition(cond, ctx)
            elif group_name == "price":
                ok, score = _evaluate_price_condition(cond, ctx)
            else:
                ok, score = _evaluate_time_condition(cond, ctx)

            total_score += score
            total_count += 1
            group_details.append({"condition": cond, "ok": ok, "score": score})

            if required and not ok:
                all_required_passed = False
        details[group_name] = group_details

    confidence = total_score / total_count if total_count else 1.0
    return all_required_passed, confidence, details


def _evaluate_projection(template: dict[str, Any], ctx: dict[str, float]) -> dict[str, Any]:
    """计算模板的支撑、阻力、目标位与止损。"""
    projection = template.get("projection", {})
    result: dict[str, Any] = {}
    for key in ("support", "resistance", "target", "stop_loss"):
        formula = projection.get(key)
        if isinstance(formula, (int, float)):
            result[key] = float(formula)
        elif isinstance(formula, str):
            result[key] = _safe_eval(formula, ctx)
        else:
            result[key] = None
    result["suggestion"] = projection.get("suggestion", "neutral")
    result["probability_prior"] = projection.get("probability_prior", 0.5)
    return result


def _deduplicate_matches(
    matches: list[dict[str, Any]],
    window: int = 3,
) -> list[dict[str, Any]]:
    """对同一模板在相邻 K 线的重复匹配进行去重，保留置信度最高的一条。"""
    if not matches:
        return matches

    key = lambda m: (m["template_name"], m["matched_index"] // window)
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for match in matches:
        groups.setdefault(key(match), []).append(match)

    result: list[dict[str, Any]] = []
    for group in groups.values():
        result.append(max(group, key=lambda m: m["confidence"]))
    result.sort(key=lambda m: (m["matched_index"], m["template_name"]))
    return result


def _match_single_template(
    df: pd.DataFrame,
    template: dict[str, Any],
    min_confidence: float = 0.5,
    feat_df: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """对单个模板在整段数据上进行匹配。

    Args:
        feat_df: 可选的预计算特征 DataFrame。若提供，则跳过本模板内部的
            ``_prepare_features`` 调用，避免多个模板重复计算相同的 Swing
            与趋势强度特征。
    """
    if feat_df is None:
        swing_order = template.get("swing_order", 2)
        feat_df = _prepare_features(df, swing_order)
    events = _build_event_list(feat_df)

    sequence = template["structure"]["sequence"]
    needed = len(sequence)
    min_required_bars = template.get("min_required_bars", 20)
    start_index = max(needed - 1, min_required_bars - 1, 1)

    direction_hint = template.get("direction", "both")
    matches: list[dict[str, Any]] = []

    for i in range(start_index, len(feat_df)):
        historical_events = [e for e in events if e["idx"] <= i]
        if len(historical_events) < needed - 1:
            # 至少还需要一个当前 K 线作为合成事件
            continue

        events_with_current = _append_synthetic_events(historical_events, feat_df, i)

        candidate_sets: list[list[dict[str, Any]] | None] = [
            _find_last_matching_subsequence(events_with_current, sequence),
            _find_last_matching_subsequence(historical_events, sequence),
        ]

        matched = False
        for candidate_events in candidate_sets:
            if candidate_events is None:
                continue
            ctx = _build_context(candidate_events, sequence, feat_df, i, direction_hint)
            if ctx is None:
                continue
            passed, confidence, _ = _evaluate_conditions(template, ctx)
            if passed and confidence >= min_confidence:
                projection = _evaluate_projection(template, ctx)
                timestamp = None
                if "timestamp" in feat_df.columns:
                    timestamp = feat_df["timestamp"].iloc[i]

                match = {
                    "template_name": template["name"],
                    "matched_index": i,
                    "matched_timestamp": timestamp,
                    "direction": direction_hint,
                    "confidence": round(confidence, 4),
                    **projection,
                }
                matches.append(match)
                matched = True
                break
        if matched:
            continue

    return _deduplicate_matches(matches)


def match_templates(
    df: pd.DataFrame,
    templates: str | Path | list[dict] | None = None,
    min_confidence: float = 0.5,
) -> list[dict[str, Any]]:
    """对 DataFrame 运行全部模板并返回匹配结果。

    默认模板目录下的所有模板 Swing order 相同时，特征（Swing 点、趋势强度、
    ATR）只计算一次并在模板间复用，显著降低冷生成路径的模板匹配延迟。

    Args:
        df: OHLC DataFrame，必须包含 ``open`` / ``high`` / ``low`` / ``close``。
        templates: 模板目录、文件、已解析模板列表或 ``None``（默认目录）。
        min_confidence: 最小置信度阈值，低于该值的候选被过滤。

    Returns:
        匹配结果列表，每个元素包含 ``template_name``、``matched_index``、
        ``confidence``、``support``、``resistance``、``target``、``stop_loss``、
        ``probability_prior`` 等字段。
    """
    _ensure_ohlc(df)
    template_list = load_templates(templates)

    # 按 swing_order 分组，同一组只计算一次特征，避免每个模板重复昂贵的
    # identify_swing_points / add_trend_strength_features 调用。
    grouped: dict[int, list[dict[str, Any]]] = {}
    for template in template_list:
        swing_order = template.get("swing_order", 2)
        grouped.setdefault(swing_order, []).append(template)

    matches: list[dict[str, Any]] = []
    for swing_order, group_templates in grouped.items():
        feat_df = _prepare_features(df, swing_order)
        for template in group_templates:
            matches.extend(
                _match_single_template(df, template, min_confidence, feat_df=feat_df)
            )

    matches.sort(key=lambda m: (m["matched_index"], m["template_name"]))
    return matches
