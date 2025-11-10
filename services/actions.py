from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class UIAction:
    """Framework-agnostic UI action descriptor.

    This does not depend on Qt/Tk. GUI layers can adapt it to QAction,
    buttons, menu items, etc.
    """
    id: str
    text: str
    callback: Callable[[], None]
    shortcut: Optional[str] = None
    checkable: bool = False


class ActionRegistry:
    """Central registry for UI actions used by menus/toolbar/ribbon.

    Register actions once in the controller and reuse everywhere.
    """

    def __init__(self) -> None:
        self._actions: Dict[str, UIAction] = {}

    def register(self, action: UIAction) -> None:
        if action.id in self._actions:
            # Last write wins; allows incremental overrides
            pass
        self._actions[action.id] = action

    def add(self, id: str, text: str, callback: Callable[[], None], *, shortcut: Optional[str] = None, checkable: bool = False) -> UIAction:
        act = UIAction(id=id, text=text, callback=callback, shortcut=shortcut, checkable=checkable)
        self.register(act)
        return act

    def get(self, id: str) -> UIAction:
        return self._actions[id]

    def try_get(self, id: str) -> Optional[UIAction]:
        return self._actions.get(id)

    def all(self) -> List[UIAction]:
        return list(self._actions.values())










