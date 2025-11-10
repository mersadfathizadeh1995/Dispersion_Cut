from __future__ import annotations


def remove_legend(ax):
    leg = ax.get_legend()
    if leg is not None:
        leg.remove()


def patch_toolbar_home(fig, on_after=None):
    try:
        toolbar = fig.canvas.manager.toolbar
        if toolbar is None:
            return
        if hasattr(toolbar, "_masw_home_patched"):
            return
        orig = toolbar.home
        def _wrapped(*args, **kwargs):
            orig(*args, **kwargs)
            if on_after:
                try:
                    on_after()
                finally:
                    try:
                        fig.canvas.draw_idle()
                    except Exception:
                        pass
        toolbar.home = _wrapped
        toolbar._masw_home_patched = True
    except Exception:
        pass

