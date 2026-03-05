import importlib.util
import os

_utils_path = os.path.join(
    os.path.dirname(__file__),
    "custom_components",
    "ica",
    "utils.py",
)
_spec = importlib.util.spec_from_file_location("ica_utils", _utils_path)
_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_utils)

normalize_product_name = _utils.normalize_product_name

test_cases = [
    "Äpplet",
    "Äpple",
    "Äpplen",
    "Barnen",
    "Barn",
    "Apples",
    "Apple",
    "Tomater",
    "Tomat",
    "  Tomater  ",
    "Oranges",
]

for test in test_cases:
    result = normalize_product_name(test)
    print(f"{test:20} → {result}")
