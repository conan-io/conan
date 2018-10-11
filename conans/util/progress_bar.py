
import os
from tqdm import tqdm
from contextlib import contextmanager

TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'


class _FileReaderWithProgressBar(object):

    tqdm_defaults = {'unit': 'B',
                     'unit_scale': True,
                     'unit_divisor': 1024,
                     'ascii': False,  # Fancy output (forces unicode progress bar)
                     }

    def __init__(self, fileobj, output, desc=None):
        pb_kwargs = self.tqdm_defaults.copy()
        self._ori_output = output

        # If there is no terminal, just print a beat every TIMEOUT_BEAT seconds.
        if not output.is_terminal:
            output = _NoTerminalOutput(output)
            pb_kwargs['mininterval'] = TIMEOUT_BEAT_SECONDS

        self._output = output
        self._fileobj = fileobj
        self.seek(0, os.SEEK_END)
        self._pb = tqdm(total=self.tell(), desc=desc, file=output, **pb_kwargs)
        self.seek(0)

    def seekable(self):
        return self._fileobj.seekable()

    def seek(self, *args, **kwargs):
        return self._fileobj.seek(*args, **kwargs)

    def tell(self):
        return self._fileobj.tell()

    def read(self, size):
        prev = self.tell()
        ret = self._fileobj.read(size)
        self._pb.update(self.tell() - prev)
        return ret

    def pb_close(self):
        self._pb.close()

    def pb_write(self, message):
        """ Allow to write messages to output without interfering with the progress bar """
        tqdm.write(message, file=self._ori_output)


class _NoTerminalOutput(object):
    """ Helper class: Replace every message sent to it with a fixed one """
    def __init__(self, output):
        self._output = output

    def write(self, *args, **kwargs):
        self._output.write(TIMEOUT_BEAT_CHARACTER)

    def flush(self):
        self._output.flush()


@contextmanager
def open_binary(path, output, **kwargs):
    with open(path, mode='rb') as f:
        file_wrapped = _FileReaderWithProgressBar(f, output=output, **kwargs)
        yield file_wrapped
        file_wrapped.pb_close()
        if not output.is_terminal:
            output.write("\n")
