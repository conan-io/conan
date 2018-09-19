
import os
import logging
from tqdm import tqdm
from contextlib import contextmanager

from conans.client.output import ConanOutput
from conans.util.log import logger


TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'

# TODO: Move these defaults somewhere else
tqdm_file_defaults = {'unit': 'B',
                      'unit_scale': True,
                      'unit_divisor': 1024,
                      'ascii': False,  # Fancy output (forces unicode progress bar)
                      }


@contextmanager
def progress_bar(output, *args, **kwargs):
    assert isinstance(output, ConanOutput)
    original_stream = output._stream
    original_log_handlers = logger.handlers.copy()

    try:
        # if not terminal, just output dots for progress bar
        pb_stream = original_stream
        if not output.is_terminal:
            pb_stream = _NoTerminalOutput(original_stream)
            kwargs.update({'mininterval': TIMEOUT_BEAT_SECONDS})

        # Pipe output through progress bar in order no to interfere with it
        class ForwardTqdm(object):

            def write(self, msg):
                tqdm.write(msg.strip('\n\r'), file=original_stream)

            def flush(self):
                original_stream.flush()

        output._stream = ForwardTqdm()

        # Pipe log through progress bar too
        class TqdmHandler(logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)  # TODO: Add conan formatting here
                    tqdm.write(msg)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    self.handleError(record)

        for hdlr in logger.handlers[:]:  # TODO: Sólo hay que eliminar los handlers de consola
            logger.removeHandler(hdlr)
        logger.addHandler(TqdmHandler())

        pb = tqdm(file=pb_stream, position=None, leave=False, *args, **kwargs)
        yield pb
        output.success("{} [done!]".format(kwargs.get('desc', '')))
        pb.close()

        if not output.is_terminal:
            output.writeln("")
    except Exception as exc:
        raise exc
    finally:
        output._stream = original_stream
        logger.handlers = original_log_handlers


class _NoTerminalOutput(object):
    """ Helper class: Replace every message sent to it with a fixed one """
    def __init__(self, output):
        self._output = output

    def write(self, *args, **kwargs):
        self._output.write(TIMEOUT_BEAT_CHARACTER)

    def flush(self):
        self._output.flush()


if __name__ == '__main__':
    import sys
    import time

    output = ConanOutput(sys.stdout, True)
    output.writeln("This is ConanOutput")
    output.info("Info message")
    output.error("ERROR message")
    logger.critical("critical before finished!")

    with progress_bar(iterable=range(10), output=output) as pb:
        for it in pb:
            # print(it)
            pb.update()
            output.write("Up to {}".format(it))
            output.info("Info inside")
            output.error("ERROR inside")
            logger.critical("critical")
            time.sleep(0.5)
    output.writeln("Finished!")
    output.info("Info after")
    output.error("Error after")
    logger.critical("critical after finished!")

