import os
from contextlib import contextmanager
import time

from tqdm import tqdm

TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'


class FileReaderWithProgressBar(object):
    def __init__(self, fileobj, output, desc=None):
        self._tqdm_bar = None
        self._fileobj = fileobj
        self.seek(0, os.SEEK_END)
        self._total_size = self.tell()
        self.seek(0)
        self._file_iterator = iter(self.file_iterable())
        self._desc = desc
        self._output = output
        self._last_time = time.time()
        if self._output and self._output.is_terminal:
            self._tqdm_bar = tqdm(total=self._total_size, desc=desc, file=self._output, unit="B",
                                  leave=True, dynamic_ncols=False, ascii=True, unit_scale=True,
                                  unit_divisor=1024)

    def description(self):
        return self._desc

    def seekable(self):
        return self._fileobj.seekable()

    def seek(self, *args, **kwargs):
        return self._fileobj.seek(*args, **kwargs)

    def tell(self):
        return self._fileobj.tell()

    def read(self, size):
        prev = self.tell()
        ret = self._fileobj.read(size)
        self.update_progress(self.tell() - prev)
        return ret

    def update_progress(self, size):
        if self._tqdm_bar is not None:
            self._tqdm_bar.update(size)
        elif self._output and time.time() - self._last_time > TIMEOUT_BEAT_SECONDS:
            self._last_time = time.time()
            self._output.write(TIMEOUT_BEAT_CHARACTER)

    def __len__(self):
        return self._total_size

    def file_iterable(self):
        chunk_size = 1024
        while True:
            data = self._fileobj.read(chunk_size)
            if data:
                self.update_progress(chunk_size)
                yield data
            else:
                break

    def __iter__(self):
        return self._file_iterator.__iter__()

    def pb_close(self):
        if self._tqdm_bar is not None:
            self._tqdm_bar.close()


class DownloadProgress(object):
    def __init__(self, length, output, description):
        self._tqdm_bar = None
        self._total_length = length
        self._output = output
        self._download_size = 0
        self._downloaded_chunks = 0
        self._description = description
        if self._output and self._output.is_terminal and self._description:
            self._tqdm_bar = tqdm(total=self._total_length,
                                  desc=self._description,
                                  file=self._output, unit="B",
                                  leave=True, dynamic_ncols=False, ascii=True, unit_scale=True,
                                  unit_divisor=1024)

    @property
    def download_size(self):
        return self._download_size

    def pb_update(self, chunk_size):
        if self._tqdm_bar is not None:
            self._tqdm_bar.update(chunk_size)

    def update(self, chunks, chunk_size=1):
        for chunk in chunks:
            yield chunk
            self._download_size += len(chunk)
            self._downloaded_chunks += 1
            if self._total_length < chunk_size*self._downloaded_chunks:
                self.pb_update(self._total_length)
            else:
                self.pb_update(chunk_size)

        if self._total_length > chunk_size * self._downloaded_chunks:
            self.pb_update(self._total_length - chunk_size * self._downloaded_chunks)

        self.pb_close()
        if self._output and not self._output.is_terminal:
            self._output.writeln("\n")

    def pb_close(self):
        if self._tqdm_bar is not None:
            self._tqdm_bar.close()


class _FileListIteratorWithProgressBar(object):

    def __init__(self, files_list, output, desc=None):
        self._files_list = files_list
        self._last_progress = None
        self._i_file = 0
        self._output = output
        self._desc = desc
        if self._output and not self._output.is_terminal:
            output.write("[")
        elif self._output:
            self._tqdm_bar = tqdm(total=len(files_list), desc=desc, file=self._output, unit="files",
                                  leave=True, dynamic_ncols=False, ascii=True)

    def description(self):
        return self._desc

    def update(self):
        self._i_file = self._i_file + 1
        units = min(50, int(50 * self._i_file / len(self._files_list)))
        if self._last_progress != units:  # Avoid screen refresh if nothing has change
            if self._output and not self._output.is_terminal:
                self._output.write('=' * (units - (self._last_progress or 0)))
            self._last_progress = units
        if self._output and self._output.is_terminal:
            self._tqdm_bar.update()

    def pb_close(self):
        if self._output and self._output.is_terminal:
            self._tqdm_bar.close()
        elif self._output:
            self._output.writeln("]")

    def __iter__(self):
        return self._files_list.__iter__()

    def __next__(self):
        return self._files_list.__iter__().__next__()


@contextmanager
def open_binary(path, output, **kwargs):
    with open(path, mode='rb') as f:
        file_wrapped = FileReaderWithProgressBar(f, output=output, **kwargs)
        yield file_wrapped
        file_wrapped.pb_close()
        if not output.is_terminal:
            output.writeln("\n")


@contextmanager
def open_file_list(files_list, output, **kwargs):
    list_wrapped = _FileListIteratorWithProgressBar(files_list, output=output, **kwargs)
    yield list_wrapped
    list_wrapped.pb_close()
    if output and not output.is_terminal:
        output.writeln("\n")
