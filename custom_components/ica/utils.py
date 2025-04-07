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
        return [{"op": "+", key: row_id, "new": new}]
    if removed:
        return [{"op": "-", key: row_id, "old": old}]

    diffs = []
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
            diffs.append(
                {"op": "~", key: row_id, "changed_props": props, "old": o, "new": n}
            )
        else:
            diffs.append({"op": "~", key: row_id, "changed_props": props})
    return diffs


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
