from talon import Module, Context, actions, ui, storage, types
from typing import Optional, Any
import logging

# TALON WINDOW MANAGEMENT API ISSUES ON UBUNTU 22.04:
# - number of workspaces gets stuck at wrong value
#   might have to do with multiple monitors
#   haven't seen anything in the log but haven't checked thoroughly
# - restoring emacs window rect moves it :(
# - something else about visible rects (multiple monitors?)

mod = Module()
ctx = Context()

mod.list('window_layout', desc="Names of window layouts")
def layout_list_update():
    # TODO: keys takes a pattern argument, not sure how it works
    LAYOUT_PREFIX = 'user.layout/layout/'
    layouts = ctx.lists['self.window_layout'] = [
        x[len(LAYOUT_PREFIX):] for x in storage.keys()
        if x.startswith(LAYOUT_PREFIX)]
    logging.info(f'layouts: {layouts}')
    return layouts
layout_list_update()

def serialize_window(w):
    return {'id': w.id,
            'title': w.title,
            'app.name': w.app.name,
            'hidden': w.hidden,
            'rect': w.rect,
            'screen.name': w.screen.name,
            'workspace': w.workspace,
            }

@mod.action_class
class ModuleActions:
    def layout_get(name: str) -> Any:
        """Returns info about saved window positions."""
        return storage.get(f'self.layout/layout/{name}')

    # TODO: store version numbers for backward compat.
    # maybe timestamps so we can see how old the layout is?
    def layout_save(name: str):
        """Remembers window positions for windows on current workspace."""
        layout = [serialize_window(w)
                  for w in ui.windows()
                  if w.workspace == ui.active_workspace()]
        storage.set(f'self.layout/layout/{name}', layout)
        layout_list_update()

    def layout_clear(name: str):
        """Forgets window positions."""
        storage.remove(f'self.layout/layout/{name}')
        layout_list_update()

    # TODO: restore workspaces?
    # TODO: heuristics if the ids don't match, eg. use title & app name?
    def layout_restore(name: Optional[str] = None):
        """Restore window positions"""
        # If the window stacking order has changed just before calling this it
        # may not be respected by the order of ui.windows(). Hence this long delay.
        actions.sleep('650ms')

        layout = actions.user.layout_get(name)
        index = {w['id']: w for w in layout}
        moved_windows = 0

        # Reversed to avoid changing stacking order (moving windows puts them on
        # top of the stack).
        for w in reversed(ui.windows()):
            try: desc = index.pop(w.id)
            except KeyError:
                w.rect = w.rect # push to top
                continue
            if w.rect == desc['rect']:
                if not moved_windows: continue
                # Hack to force raising the window to top of stacking order.
                r = w.rect
                r.x += 1
                w.rect = r
            moved_windows += 1
            w.rect = desc['rect']

        # Print some stats.
        failed = len(index)
        if 0 < failed == len(layout):
            logging.warning("Could not restore any windows!")
        elif failed:
            logging.warning(f"Could not restore {failed} windows: " +
                            ''.join('\n  ' + str(v) for v in index.values()))
        avoided_moving = len(layout) - failed - moved_windows
        if avoided_moving:
            logging.info(f"Avoided moving {avoided_moving} windows")
