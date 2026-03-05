import logging
import json
from typing import Any, TypeVar

_DataT = TypeVar("_DataT", default=dict[Any, Any])


class EmptyLogger(logging.Logger):
    """Acts as an dumb logger that doesn't actually log anything"""

    def __init__(self):
        self.disabled = True


def trim_props(obj: _DataT, predicate=None) -> _DataT:
    if not obj:
        return obj
    predicate = predicate or (lambda k, v: v is not None and v != "")
    return {k: v for k, v in obj.items() if predicate(k, v)}


def to_dict(list_source, key: str = "id"):
    return {value[key]: value for value in list_source} if list_source else {}


def get_diffs(a, b, key: str = "id", include_values: bool = True):
    if isinstance(a, list):
        a = to_dict(a, key)
    if isinstance(b, list):
        b = to_dict(b, key)

    added = b.keys() - a.keys()
    removed = a.keys() - b.keys()
    diffs = [{"op": "+", key: row_id, "new": b[row_id]} for row_id in added]
    diffs.extend([{"op": "-", key: row_id, "old": a[row_id]} for row_id in removed])

    a_set = set(a)
    # aa = {k: v for k,v in a.items()}
    # aa_set = set(a.keys())
    b_set = set(b)
    # bb = {x[key]: x for x in b}
    # bb = b.keys()
    # bb_set = set(bb)
    remaining = a_set.intersection(b_set)
    # remaining = aa_set.intersection(bb_set)

    for row_id in remaining:
        old = a[row_id]
        new = b[row_id]
        props = []
        for k in new:
            d = new.get(k, None) != old.get(k, None)
            # todo: ignore changes in ordering when list. ICA quite oftenly change or send inconsistent sorting in the Ean-property
            if d:
                props.append(k)
        if props:
            if include_values:
                o = {value: old.get(value, None) for value in props}
                n = {value: new.get(value, None) for value in props}
                diffs.append(
                    {"op": "~", key: row_id, "changed_props": props, "old": o, "new": n}
                )
            else:
                diffs.append({"op": "~", key: row_id, "changed_props": props})
    return diffs


def get_diff_obj(old: dict, new: dict, key: str = "id", include_values: bool = True):
    added = not bool(old) and bool(new)
    removed = bool(old) and not bool(new)
    old = old or {}
    new = new or {}
    row_id = new.get(key) or old.get(key)
    if added:
        return {"op": "+", key: row_id, "new": new}
    if removed:
        return {"op": "-", key: row_id, "old": old}

    props = []
    for k in [*old, *new]:
        d = new.get(k, None) != old.get(k, None)
        # todo: ignore changes in ordering when list. ICA quite oftenly change or send inconsistent sorting in the Ean-property
        if d and k not in props:
            props.append(k)

    if props:
        if include_values:
            o = {value: old.get(value, None) for value in props}
            n = {value: new.get(value, None) for value in props}
            return {"op": "~", key: row_id, "changed_props": props, "old": o, "new": n}
        else:
            return {"op": "~", key: row_id, "changed_props": props}
    return None


def index_of(source: list[dict], key, value) -> int:
    """Return the index of the item with the given KeyValue pairing or -1 if not found."""
    return next(
        (index for index, item in enumerate(source) if item.get(key) == value),
        -1,
    )


def try_parse_int(value: Any) -> tuple[bool, int]:
    """Try parsing a value as int. Return as a tuple."""
    try:
        return (True, int(value))
    except ValueError:
        return (False, 0)


# ---------------------------------------------------------------------------
# Unit conversion system
# Supported units: L, dl, cl, ml, krm, tsk, msk, kg, g, st, förp
# ---------------------------------------------------------------------------

# Volume – conversion factors to the base unit (ml)
_VOLUME_TO_ML: dict[str, float] = {
    "l": 1000.0,
    "dl": 100.0,
    "cl": 10.0,
    "ml": 1.0,
    "krm": 1.0,   # kryddmått  ≈ 1 ml
    "tsk": 5.0,    # tesked     (teaspoon) = 5 ml
    "msk": 15.0,   # matsked    (tablespoon) = 15 ml
}

# Weight – conversion factors to the base unit (g)
_WEIGHT_TO_G: dict[str, float] = {
    "kg": 1000.0,
    "g": 1.0,
}

# Count units – not inter-convertible ('st' = styck/pieces, 'förp' = förpackning/packs)
_COUNT_UNITS: set[str] = {"st", "förp"}

# Grouped table look-ups
_UNIT_GROUPS: dict[str, dict[str, float]] = {
    "volume": _VOLUME_TO_ML,
    "weight": _WEIGHT_TO_G,
}


def _normalize_unit(unit: str | None) -> str | None:
    """Lowercase / strip a unit string for comparison."""
    if unit is None:
        return None
    return unit.strip().lower()


def get_unit_group(unit: str | None) -> tuple[str | None, dict[str, float] | None]:
    """Return ``(group_name, conversion_table)`` for *unit*.

    Count units each get their own group (``"count:st"``, ``"count:förp"``)
    so that ``st`` and ``förp`` are **not** treated as inter-convertible.

    Returns ``(None, None)`` for unrecognised units.
    """
    norm = _normalize_unit(unit)
    if norm is None:
        return (None, None)
    for group_name, table in _UNIT_GROUPS.items():
        if norm in table:
            return (group_name, table)
    if norm in _COUNT_UNITS:
        # Each count unit is its own isolated group
        return (f"count:{norm}", {norm: 1.0})
    return (None, None)


def are_units_compatible(unit_a: str | None, unit_b: str | None) -> bool:
    """Return ``True`` if two units can be converted between each other."""
    norm_a = _normalize_unit(unit_a)
    norm_b = _normalize_unit(unit_b)
    if norm_a is None and norm_b is None:
        return True
    if norm_a is None or norm_b is None:
        return False
    if norm_a == norm_b:
        return True
    group_a, _ = get_unit_group(unit_a)
    group_b, _ = get_unit_group(unit_b)
    return group_a is not None and group_a == group_b


def convert_quantity(
    quantity: float, from_unit: str, to_unit: str
) -> float | None:
    """Convert *quantity* from *from_unit* to *to_unit*.

    Returns ``None`` when the units are incompatible.
    Conversions are rounded to 4 decimal places to avoid floating-point noise.
    """
    from_norm = _normalize_unit(from_unit)
    to_norm = _normalize_unit(to_unit)
    if from_norm is None or to_norm is None:
        return None
    if from_norm == to_norm:
        return quantity

    from_group, from_table = get_unit_group(from_unit)
    to_group, to_table = get_unit_group(to_unit)

    if from_group is None or to_group is None or from_group != to_group:
        return None

    # from → base → to
    base_value = quantity * from_table[from_norm]
    return round(base_value / to_table[to_norm], 4)


# ---------------------------------------------------------------------------
# Merging IcaShoppingListEntry dicts
# ---------------------------------------------------------------------------

def _merge_recipe_refs(
    base_recipes: list[dict] | None,
    other_recipes: list[dict] | None,
) -> list[dict] | None:
    """Merge two recipe-reference lists.

    * Quantities for matching recipe IDs are summed (with unit conversion).
    * Non-overlapping recipe references are included as-is.
    * Returns ``None`` when both inputs are ``None``.
    """
    if not base_recipes and not other_recipes:
        return None
    if not other_recipes:
        return [dict(r) for r in base_recipes] if base_recipes else None
    if not base_recipes:
        return [dict(r) for r in other_recipes]

    merged: dict[int, dict] = {}
    for ref in base_recipes:
        rid = ref.get("id")
        merged[rid] = dict(ref)

    for ref in other_recipes:
        rid = ref.get("id")
        if rid in merged:
            existing = merged[rid]
            other_qty = ref.get("quantity", 0) or 0
            existing_qty = existing.get("quantity", 0) or 0
            converted = convert_quantity(
                other_qty,
                ref.get("unit", "") or "",
                existing.get("unit", "") or "",
            )
            if converted is not None:
                existing["quantity"] = round(existing_qty + converted, 4)
            # else: incompatible units for same recipe – keep existing value
        else:
            merged[rid] = dict(ref)

    return list(merged.values())


def merge_shopping_list_entries(
    base: dict,
    other: dict,
) -> dict:
    """Merge two ``IcaShoppingListEntry`` dicts together.

    *base* is treated as the primary entry; *other* is merged **into** it.

    Merging rules
    -------------
    * ``quantity`` - summed when the ``unit`` values are compatible.
      If only one entry carries a quantity the non-None value is kept.
    * ``unit`` - the *base* unit is preserved when both have quantities;
      if only *other* has a unit it is adopted.
    * ``recipes`` - recipe reference lists are combined; quantities for
      the same ``recipeId`` are added (with unit conversion when needed).
    * Other nullable fields (``productEan``, ``articleGroupId``, etc.) are
      carried over from *other* when *base* has ``None``.

    Parameters
    ----------
    base:  The existing / primary shopping-list entry.
    other: The entry to merge into *base*.

    Returns
    -------
    A **new** dict with the merged result (neither input is mutated).
    """
    result = dict(base)

    base_qty: float | None = base.get("quantity")
    other_qty: float | None = other.get("quantity")
    base_unit: str | None = base.get("unit")
    other_unit: str | None = other.get("unit")

    if base_qty is not None and other_qty is not None:
        # Both entries carry a quantity – try to add them
        if base_unit is None and other_unit is None:
            result["quantity"] = round(base_qty + other_qty, 4)
        elif base_unit is not None and other_unit is not None:
            converted = convert_quantity(other_qty, other_unit, base_unit)
            if converted is not None:
                result["quantity"] = round(base_qty + converted, 4)
            # else: incompatible units → keep base quantity unchanged
        elif base_unit is None and other_unit is not None:
            # Base has no unit context – adopt other's unit system
            result["quantity"] = round(base_qty + other_qty, 4)
            result["unit"] = other_unit
        # else: other_unit is None → just add raw numbers, keep base_unit
        else:
            result["quantity"] = round(base_qty + other_qty, 4)
    elif base_qty is None and other_qty is not None:
        result["quantity"] = other_qty
        if other_unit is not None:
            result["unit"] = other_unit
    # else: base_qty wins (may itself be None)

    # Merge recipe references
    merged_recipes = _merge_recipe_refs(
        base.get("recipes"), other.get("recipes")
    )
    if merged_recipes is not None:
        result["recipes"] = merged_recipes

    # Carry over non-None fields from 'other' when 'base' has None
    for field in (
        "productEan",
        "articleGroupId",
        "articleGroupIdExtended",
        "offerId",
    ):
        if result.get(field) is None and other.get(field) is not None:
            result[field] = other[field]

    return result


if __name__ == "__main__":
    print("Testing `get_diffs(old, new)`")
    # o = [{"id": 1, "name": "OLD"}, {"id": 3, "name": "gone!"}]
    # n = [{"id": 1, "name": "FOO"}, {"id": 2, "name": "BAR"}]

    j = open(
        "C:\\HomeAssistant\\config\\.storage\\ica.offers_event_data_diff_base2.json",
        "r",
    ).read()
    doc = json.loads(j)
    o = doc["value"]["old"]
    n = doc["value"]["new"]
    print(o)
    print(n)
    print(get_diffs(o, n))
