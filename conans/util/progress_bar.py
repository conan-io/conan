
import six
import copy
import logging
from tqdm import tqdm
from contextlib import contextmanager

from conans.client.output import ConanOutput
from conans.util.log import logger


TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = six.u('.')


tqdm_file_defaults = {'unit': 'B',
                      'unit_scale': True,
                      'unit_divisor': 1024,
                      'ascii': False,  # Fancy output (forces unicode progress bar)
                      }


@contextmanager
def progress_bar(output, *args, **kwargs):
    if not output:  # Just fake it.
        yield tqdm(disable=True)
        return

    assert isinstance(output, ConanOutput)
    original_stream = output._stream
    original_log_handlers = copy.copy(logger.handlers)
    original_is_terminal = output.is_terminal

    try:
        # if not terminal, just output dots for progress bar
        pb_stream = original_stream
        if not original_is_terminal:
            pb_stream = _NoTerminalOutput(original_stream)
            kwargs.update({'mininterval': TIMEOUT_BEAT_SECONDS})

        # Pipe output through progress bar in order no to interfere with it
        output._stream = _ForwardTqdm(original_stream)

        # Pipe log through progress bar too
        for hdlr in logger.handlers[:]:  # TODO: Remove only console handlers
            logger.removeHandler(hdlr)
        logger.addHandler(_TqdmHandler())

        pb = tqdm(file=pb_stream, position=None, leave=False, *args, **kwargs)
        yield pb
        pb.close()
        if not original_is_terminal:
            output.writeln("")
        output.write("{} [done]".format(kwargs.get('desc', '')))
    except Exception as exc:
        raise exc
    finally:
        output._stream = original_stream
        logger.handlers = original_log_handlers


class _TqdmHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)  # TODO: Add conan formatting here
            tqdm.write(msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class _ForwardTqdm(object):
    def __init__(self, original_stream):
        self._original_stream = original_stream

    def write(self, msg):
        tqdm.write(msg.strip('\n\r'), end=six.u('\n'), file=self._original_stream)

    def flush(self):
        self._original_stream.flush()


class _NoTerminalOutput(object):
    """ Helper class: Replace every message sent to it with a fixed one """
    def __init__(self, output):
        self._output = output

    def write(self, *args, **kwargs):
        self._output.write(TIMEOUT_BEAT_CHARACTER)

    def flush(self):
        self._output.flush()
