from bottle import HTTPResponse

from conans.errors import ConanException


class ReturnHandlerPlugin(object):
    """ The ReturnHandlerPlugin plugin unify REST return and exception management """

    name = 'ReturnHandlerPlugin'
    api = 2

    def __init__(self, exception_mapping):
        self.exception_mapping = exception_mapping

    def setup(self, app):
        """ Make sure that other installed plugins don't affect the same
            keyword argument. """
        for other in app.plugins:
            if not isinstance(other, ReturnHandlerPlugin):
                continue

    def apply(self, callback, _):
        """ Apply plugin """
        def wrapper(*args, **kwargs):
            """ Capture possible exceptions to manage the return """
            try:
                # The encoding from browsers is utf-8, so we assume it
                for key, value in kwargs.items():
                    if isinstance(value, str):
                        kwargs[key] = value
                return callback(*args, **kwargs)  # kwargs has :xxx variables from url
            except HTTPResponse:
                raise
            except ConanException as excep:
                return get_response_from_exception(excep, self.exception_mapping)
            except Exception as e:
                # logger.error(e)
                # logger.error(traceback.print_exc())
                return get_response_from_exception(e, self.exception_mapping)

        return wrapper


def get_response_from_exception(excep, exception_mapping):
    status = exception_mapping.get(excep.__class__, None)
    if status is None:
        status = 500
    ret = HTTPResponse(status=status, body=str(excep))
    ret.add_header("Content-Type", "text/plain")
    return ret
