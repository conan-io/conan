from threading import Thread


class ExceptionThread(Thread):
    def run(self):
        self._exc = None
        try:
            super().run()
        except Exception as e:
            self._exc = e

    def join(self, timeout=None):
        super().join(timeout=timeout)

    def raise_errors(self):
        if self._exc:
            raise self._exc
