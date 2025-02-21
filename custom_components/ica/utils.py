import logging


class EmptyLogger(logging.Logger):
    """Acts as an dumb logger that doesn't actually log anything"""

    def __init__(self):
        self.disabled = True


def to_dict(list_source, key: str = "id"):
    if not list_source:
        return {}
    return {value[key]: value for index, value in enumerate(list_source)}


def get_diffs(a, b, key: str = "id"):
    diffs = []
    if isinstance(a, list):
        a = to_dict(a, key)
    if isinstance(b, list):
        b = to_dict(b, key)

    added = b.keys() - a.keys()
    removed = a.keys() - b.keys()
    diffs.extend(list({"op": "+", key: row_id, "new": b[row_id]} for row_id in added))
    diffs.extend(list({"op": "-", key: row_id, "old": a[row_id]} for row_id in removed))

    a_set = {v for v in a}
    b_set = {v for v in b}
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
            diffs.append({'op': '~', key: row_id, 'changed_props': props, 'old': o, 'new': n})

    return diffs
