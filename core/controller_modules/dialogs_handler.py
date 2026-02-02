"""Qt dialog handler for axis limits and settings.

Handles Qt-specific dialog interactions for setting plot parameters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib

if TYPE_CHECKING:
    from dc_cut.core.base_controller import BaseInteractiveRemoval


class DialogsHandler:
    """Handles Qt dialog interactions for plot settings."""

    def __init__(self, controller: "BaseInteractiveRemoval") -> None:
        """Initialize dialogs handler.

        Parameters
        ----------
        controller : BaseInteractiveRemoval
            Parent controller instance.
        """
        self._ctrl = controller

    def _is_qt_backend(self) -> bool:
        """Check if running on Qt backend."""
        return matplotlib.get_backend().lower().startswith('qt')

    def set_xlim(self, event=None) -> bool:
        """Open dialog to set frequency axis limits.

        Returns
        -------
        bool
            True if limits were set, False if cancelled or failed.
        """
        if not self._is_qt_backend():
            return False

        try:
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets

            text, ok = QtWidgets.QInputDialog.getText(
                self._ctrl.fig.canvas.manager.window,
                "X limits (Frequency)",
                "Enter xmin,xmax (e.g. 1,100):",
            )
            if not ok or not text:
                return False

            parts = [p.strip() for p in str(text).split(',') if p.strip()]
            xmin, xmax = float(parts[0]), float(parts[1])

            self._ctrl.ax_freq.set_xlim(xmin, xmax)
            try:
                self._ctrl._apply_frequency_ticks()
            except Exception:
                pass
            self._ctrl._apply_axis_limits()
            self._ctrl.fig.canvas.draw_idle()
            return True
        except Exception:
            return False

    def set_ylim(self, event=None) -> bool:
        """Open dialog to set velocity axis limits.

        Returns
        -------
        bool
            True if limits were set, False if cancelled or failed.
        """
        if not self._is_qt_backend():
            return False

        try:
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets

            text, ok = QtWidgets.QInputDialog.getText(
                self._ctrl.fig.canvas.manager.window,
                "Y limits (Velocity)",
                "Enter ymin,ymax (e.g. 0,4000):",
            )
            if not ok or not text:
                return False

            parts = [p.strip() for p in str(text).split(',') if p.strip()]
            ymin, ymax = float(parts[0]), float(parts[1])

            for ax in (self._ctrl.ax_freq, self._ctrl.ax_wave):
                ax.set_ylim(ymin, ymax)

            self._ctrl._apply_axis_limits()
            self._ctrl.fig.canvas.draw_idle()
            return True
        except Exception:
            return False

    def set_average_resolution(self, event=None) -> bool:
        """Open dialog to set average and export resolution.

        Returns
        -------
        bool
            True if resolution was set, False if cancelled or failed.
        """
        if not self._is_qt_backend():
            return False

        try:
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets

            try:
                current_avg = int(
                    getattr(self._ctrl, 'avg_points_override', 0)
                    or (
                        getattr(self._ctrl, 'bins_for_average', 30)
                        * getattr(self._ctrl, 'interp_factor', 1)
                    )
                )
            except Exception:
                current_avg = 50

            try:
                current_exp = int(getattr(self._ctrl, 'export_bins', 50))
            except Exception:
                current_exp = 50

            prompt = (
                f"Enter number of points for averages and export\n"
                f"- Single value sets both (current: avg={current_avg}, export={current_exp})\n"
                f"- Or 'avg,export' (e.g. 60,80)"
            )

            text, ok = QtWidgets.QInputDialog.getText(
                self._ctrl.fig.canvas.manager.window,
                "Average resolution",
                prompt,
            )
            if not ok or not text:
                return False

            ans = str(text).strip()
            if ',' in ans:
                a_str, e_str = ans.split(',')
                a = max(5, int(float(a_str)))
                e = max(5, int(float(e_str)))
            else:
                a = e = max(5, int(float(ans)))

            self._ctrl.avg_points_override = int(a)
            self._ctrl.export_bins = int(e)

            try:
                self._ctrl._update_average_line()
                self._ctrl._update_legend()
                self._ctrl.fig.canvas.draw_idle()
            except Exception:
                pass

            return True
        except Exception:
            return False
