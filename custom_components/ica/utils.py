import logging


class EmptyLogger(logging.Logger):
    """Acts as an dumb logger that doesn't actually log anything"""

    def __init__(self):
        self.disabled = True


def to_dict(list_source, key: str = "id"):
    return {value[key]: value for value in list_source} if list_source else {}


def get_diffs(a, b, key: str = "id"):
    if isinstance(a, list):
        a = to_dict(a, key)
    if isinstance(b, list):
        b = to_dict(b, key)

    added = b.keys() - a.keys()
    removed = a.keys() - b.keys()
    diffs = [{"op": "+", key: row_id, "new": b[row_id]} for row_id in added]
    diffs.extend([{"op": "-", key: row_id, "old": a[row_id]} for row_id in removed])

    a_set = set(a)
    b_set = set(b)
    remaining = a_set.intersection(b_set)

    for row_id in remaining:
        old = a[row_id]
        new = b[row_id]
        props = []
        for key in new:
            d = new.get(key, None) != old.get(key, None)
            if d:
                props.append(key)

        if props:
            o = {value: old.get(value, None) for value in props}
            n = {value: new.get(value, None) for value in props}
            diffs.append(
                {"op": "~", key: row_id, "changed_props": props, "old": o, "new": n}
            )

    return diffs


def index_of(source: list[dict], key, value) -> int:
    """Return the index of the item with the given KeyValue pairing or -1 if not found."""
    return next(
        (index for index, item in enumerate(source) if item.get(key) == value),
        -1,
    )
