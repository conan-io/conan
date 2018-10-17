

try:
    from contextlib import ExitStack
except OSError:

    import sys
    from collections import deque
    from types import InstanceType


    def _make_context_fixer(frame_exc):
        return lambda new_exc, old_exc: None


    def _reraise_with_existing_context(exc_details):
        exc_type, exc_value, exc_tb = exc_details
        exec("raise exc_type, exc_value, exc_tb")


    def _get_type(obj):
        obj_type = type(obj)
        if obj_type is InstanceType:
            return obj.__class__ # Old-style class
        return obj_type # New-style class


    class ExitStack(object):
        """ Taken from contextlib2 (PSF licensed) """

        def __init__(self):
            self._exit_callbacks = deque()

        def pop_all(self):
            new_stack = type(self)()
            new_stack._exit_callbacks = self._exit_callbacks
            self._exit_callbacks = deque()
            return new_stack

        def _push_cm_exit(self, cm, cm_exit):

            def _exit_wrapper(*exc_details):
                return cm_exit(cm, *exc_details)

            _exit_wrapper.__self__ = cm
            self.push(_exit_wrapper)

        def push(self, exit):
            # We use an unbound method rather than a bound method to follow
            # the standard lookup behaviour for special methods
            _cb_type = _get_type(exit)
            try:
                exit_method = _cb_type.__exit__
            except AttributeError:
                # Not a context manager, so assume its a callable
                self._exit_callbacks.append(exit)
            else:
                self._push_cm_exit(exit, exit_method)
            return exit  # Allow use as a decorator

        def callback(self, callback, *args, **kwds):
            def _exit_wrapper(exc_type, exc, tb):
                callback(*args, **kwds)

            # We changed the signature, so using @wraps is not appropriate, but
            # setting __wrapped__ may still help with introspection
            _exit_wrapper.__wrapped__ = callback
            self.push(_exit_wrapper)
            return callback  # Allow use as a decorator

        def enter_context(self, cm):
            # We look up the special methods on the type to match the with statement
            _cm_type = _get_type(cm)
            _exit = _cm_type.__exit__
            result = _cm_type.__enter__(cm)
            self._push_cm_exit(cm, _exit)
            return result

        def close(self):
            """Immediately unwind the context stack"""
            self.__exit__(None, None, None)

        def __enter__(self):
            return self

        def __exit__(self, *exc_details):
            received_exc = exc_details[0] is not None

            # We manipulate the exception state so it behaves as though
            # we were actually nesting multiple with statements
            frame_exc = sys.exc_info()[1]
            _fix_exception_context = _make_context_fixer(frame_exc)

            # Callbacks are invoked in LIFO order to match the behaviour of
            # nested context managers
            suppressed_exc = False
            pending_raise = False
            while self._exit_callbacks:
                cb = self._exit_callbacks.pop()
                try:
                    if cb(*exc_details):
                        suppressed_exc = True
                        pending_raise = False
                        exc_details = (None, None, None)
                except:
                    new_exc_details = sys.exc_info()
                    # simulate the stack of exceptions by setting the context
                    _fix_exception_context(new_exc_details[1], exc_details[1])
                    pending_raise = True
                    exc_details = new_exc_details
            if pending_raise:
                _reraise_with_existing_context(exc_details)
            return received_exc and suppressed_exc
