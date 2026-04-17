from __future__ import annotations

from typing import Tuple


def start_add_to_offset(controller, idx: int, v_new, f_new, w_new) -> None:
    """Begin an add-data session targeting an existing offset.

    Draws purple 'x' preview points and enables Save.
    """
    mkr, col = 'x', 'purple'
    lf = controller.ax_freq.plot(f_new, v_new, mkr, color=col, markersize=6, label="added")[0]
    lw = controller.ax_wave.plot(w_new, v_new, mkr, color=col, markersize=6, label="added")[0]
    controller._add_v, controller._add_f, controller._add_w = v_new, f_new, w_new
    controller._add_line_freq, controller._add_line_wave = lf, lw
    controller._added_offset_idx = idx
    controller.add_mode = True
    try: controller._enable_save_added(True)
    except Exception: pass


def start_add_new_layer(controller, layer_name: str, marker: str, colour: str, v_new, f_new, w_new) -> None:
    """Begin an add-layer session for a brand new layer with custom style."""
    lf = controller.ax_freq.plot(f_new, v_new,
                                 marker=marker, linestyle='', markerfacecolor='none',
                                 markeredgecolor=colour, markeredgewidth=1.5, markersize=6)[0]
    lw = controller.ax_wave.plot(w_new, v_new,
                                 marker=marker, linestyle='', markerfacecolor='none',
                                 markeredgecolor=colour, markeredgewidth=1.5, markersize=6,
                                 label=layer_name)[0]
    controller._add_v, controller._add_f, controller._add_w = v_new, f_new, w_new
    controller._add_line_freq, controller._add_line_wave = lf, lw
    controller._added_offset_idx = len(controller.velocity_arrays)
    controller._new_layer_info = (layer_name, marker, colour)
    controller.add_mode = True
    try: controller._enable_save_added(True)
    except Exception: pass
