"""Root test configuration and sandbox compatibility hooks."""

import sys

if sys.platform == "win32":
    import asyncio
    import selectors
    import time
    from asyncio.selector_events import BaseSelectorEventLoop

    # In sandboxed Windows environments where loopback network connect is restricted,
    # socket.socketpair() blocks in the kernel. Patch the self-pipe on BaseSelectorEventLoop
    # and provide empty-set handling for Windows select().
    orig_select = selectors.SelectSelector._select

    def _patched_select(self, r, w, _, timeout):
        if not r and not w:
            if timeout is not None and timeout > 0:
                time.sleep(min(timeout, 0.05))
            return [], [], []
        return orig_select(self, r, w, _, timeout)

    selectors.SelectSelector._select = _patched_select

    def _dummy_make_self_pipe(self):
        self._ssock = None
        self._csock = None
        self._internal_fds = 0

    def _dummy_write_to_self(self):
        pass

    def _dummy_close_self_pipe(self):
        pass

    BaseSelectorEventLoop._make_self_pipe = _dummy_make_self_pipe
    BaseSelectorEventLoop._write_to_self = _dummy_write_to_self
    BaseSelectorEventLoop._close_self_pipe = _dummy_close_self_pipe

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
