from __future__ import annotations

import os
from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets


def run_autoscale_smoke(ctrl) -> None:
    # Exercise Home
    try:
        tb = ctrl.fig.canvas.manager.toolbar
        if tb is not None and hasattr(tb, 'home'):
            tb.home()
    except Exception:
        pass
    ctrl._apply_axis_limits()
    # Resize bounce
    try:
        sz = ctrl.fig.get_size_inches()
        ctrl.fig.set_size_inches(sz[0]+0.01, sz[1]+0.01, forward=True)
        ctrl.fig.set_size_inches(*sz, forward=True)
    except Exception:
        pass
    ctrl._apply_axis_limits(); ctrl.fig.canvas.draw_idle()


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    # Minimal dataset: two points
    import numpy as np
    from dc_cut.gui.controller.composed import InteractiveRemovalWithLayers
    v = [np.array([500.0, 1500.0])]
    f = [np.array([2.0, 20.0])]
    w = [v[0] / f[0]]
    ctrl = InteractiveRemovalWithLayers(v, f, w, array_positions=np.arange(0, 48, 2.0), source_offsets=[], set_leg=["T"], receiver_dx=2.0, legacy_controls=False)
    run_autoscale_smoke(ctrl)
    # Close headless
    try:
        ctrl.fig.canvas.flush_events()
    except Exception:
        pass


if __name__ == "__main__":
    main()
