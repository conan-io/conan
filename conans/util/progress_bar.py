import os
from contextlib import contextmanager

from tqdm import tqdm

TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'


class _FileReaderWithProgressBar(object):

    tqdm_defaults = {'unit': 'B',
                     'unit_scale': True,
                     'unit_divisor': 1024,
                     'dynamic_ncols': False,
                     'leave': True,
                     'ascii': True}

    def __init__(self, fileobj, output, desc=None):
        pb_kwargs = self.tqdm_defaults.copy()

        # If there is no terminal, just print a beat every TIMEOUT_BEAT seconds.
        if not output.is_terminal:
            output = _NoTerminalOutput(output)
            pb_kwargs['mininterval'] = TIMEOUT_BEAT_SECONDS

        self._fileobj = fileobj
        self.seek(0, os.SEEK_END)
        self._tqdm_bar = tqdm(total=self.tell(), desc=desc, file=output, **pb_kwargs)
        self.seek(0)

    def description(self):
        return self._tqdm_bar.desc

    def seekable(self):
        return self._fileobj.seekable()

    def seek(self, *args, **kwargs):
        return self._fileobj.seek(*args, **kwargs)

    def tell(self):
        return self._fileobj.tell()

    def read(self, size):
        prev = self.tell()
        ret = self._fileobj.read(size)
        self._tqdm_bar.update(self.tell() - prev)
        return ret

    def pb_close(self):
        self._tqdm_bar.close()


class _NoTerminalOutput(object):
    """ Helper class: Replace every message sent to it with a fixed one """
    def __init__(self, output):
        self._output = output

    def write(self, *args, **kwargs):
        self._output.write(TIMEOUT_BEAT_CHARACTER)

    def flush(self):
        self._output.flush()


class _FileListReaderWithProgressBar(object):

    def __init__(self, files_list, output, desc=None):
        self._files_list = files_list
        self._last_progress = None
        self._i_file = 0
        self._output = output
        if not output.is_terminal:
            output.write("[")
        else:
            self._tqdm_bar = tqdm(total=len(files_list), desc=desc, file=output, unit="files",
                                  leave=True, dynamic_ncols=False, ascii=True)

    def description(self):
        return self._tqdm_bar.desc

    def update(self):
        self._i_file = self._i_file + 1
        units = min(50, int(50 * self._i_file / len(self._files_list)))
        if self._last_progress != units:  # Avoid screen refresh if nothing has change
            if not self._output.is_terminal:
                self._output.write('=' * (units - (self._last_progress or 0)))
            self._last_progress = units
        if self._output.is_terminal:
            self._tqdm_bar.update()

    def pb_close(self):
        if self._output.is_terminal:
            self._tqdm_bar.close()
        else:
            self._output.writeln("]")

    def __iter__(self):
        return self._files_list.__iter__()

    def __next__(self):
        return self._files_list.__iter__().__next__()


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
            output.writeln("\n")

@contextmanager
def open_file_list(files_list, output, **kwargs):
    list_wrapped = _FileListReaderWithProgressBar(files_list, output=output, **kwargs)
    yield list_wrapped
    list_wrapped.pb_close()
    if not output.is_terminal:
        output.writeln("\n")
