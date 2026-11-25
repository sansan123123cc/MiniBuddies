"""Window ownership and native dialogs that manage their own stacking."""

_native_dialog_depth = 0


def run_native_dialog(operation, *args, **kwargs):
    """Suspend pet-window promotion while a native picker runs its own event loop."""
    global _native_dialog_depth
    _native_dialog_depth += 1
    try:
        return operation(*args, **kwargs)
    finally:
        _native_dialog_depth -= 1


def native_dialog_open():
    return _native_dialog_depth > 0


def owner_depth(widget):
    depth = 0
    parent = widget.parentWidget()
    while parent is not None:
        depth += int(parent.isWindow())
        parent = parent.parentWidget()
    return depth
