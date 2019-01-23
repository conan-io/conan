
import os
from contextlib import contextmanager

from tqdm import tqdm
from conans.client.rest.uploader_downloader import print_progress,\
    progress_units, human_readable_progress

TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'


class _FileReaderWithConanProgressBar(object):

    def __init__(self, fileobj, output, desc=None):
        self._output = output
        self._fileobj = fileobj
        self.seek(0, os.SEEK_END)
        self.totalsize = self.tell()
        self.seek(0)
        self._last = 0

    def seekable(self):
        return self._fileobj.seekable()

    def seek(self, *args, **kwargs):
        return self._fileobj.seek(*args, **kwargs)

    def tell(self):
        return self._fileobj.tell()

    def read(self, size):
        ret = self._fileobj.read(size)
        diff = self.tell()
        if diff - self._last > self.totalsize/200.0:
            self._last = diff
            if self._output.is_terminal:
                units = progress_units(diff, self.totalsize)
                progress = human_readable_progress(diff, self.totalsize)
                print_progress(self._output, units, progress=progress)
        return ret

    def pb_close(self):
        progress = human_readable_progress(self.totalsize, self.totalsize)
        print_progress(self._output, progress_units(100, 100), progress)
        self._output.writeln("")


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
    output.writeln("Extracting %s" % os.path.basename(path))
    with open(path, mode='rb') as f:
        if output.is_terminal:
            file_wrapped = _FileReaderWithConanProgressBar(f, output=output, **kwargs)
            yield file_wrapped
            file_wrapped.pb_close()
            if not output.is_terminal:
                output.write("\n")
        else:
            yield f
