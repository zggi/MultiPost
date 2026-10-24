"""Regression guard for the v1.6.0 launch crash (QDialog used but never
imported): every Qt class name referenced in ui.py must appear in its
import lists. compileall cannot catch this - a NameError only fires at
import time, i.e. on the user's PC, after the app is shipped.
"""

import ast
import os
import re

UI_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "multipost", "ui.py")


def test_all_qt_names_used_are_imported():
    src = open(UI_PATH, encoding="utf-8").read()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and re.match(r"^Q[A-Z]", node.id):
            used.add(node.id)
        if isinstance(node, ast.Attribute) and re.match(r"^Q[A-Z]", node.attr):
            used.add(node.attr)
    # Names resolved via module prefix (Qt.AlignCenter etc.) are not bare names.
    missing = used - imported
    assert not missing, f"Qt names used but not imported in ui.py: {sorted(missing)}"
