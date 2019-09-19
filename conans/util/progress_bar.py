import os
from contextlib import contextmanager
import time

from tqdm import tqdm

from conans.util.files import mkdir, save_append, to_file_bytes

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


class _FileDownloaderWithProgressBar(object):
    def __init__(self, file_path, response, output, desc=None):
        self._tqdm_bar = None
        self._ret = bytearray()
        self._response = response
        self._file_path = file_path
        self._total_length = response.headers.get('content-length')
        self._finished_download = False
        self._output = output
        if self._total_length is None:  # no content length header
            if not file_path:
                self._ret += self._response.content
            else:
                self._total_length = len(response.content)
                self._finished_download = True
        else:
            self._total_length = int(self._total_length)

        if self._output and self._output.is_terminal and self._file_path:
            self._tqdm_bar = tqdm(total=self._total_length,
                                  desc="Downloading {}".format(os.path.basename(self._file_path)),
                                  file=self._output, unit="B",
                                  leave=True, dynamic_ncols=False, ascii=True, unit_scale=True,
                                  unit_divisor=1024)

    @property
    def finished_download(self):
        return self._finished_download

    def save(self):
        if self._tqdm_bar is not None:
            self._tqdm_bar.update(self._total_length)
        save_append(self._file_path, self._response.content)

    def file_path(self):
        if __name__ == '__main__':
            return self._file_path

    def download(self):

        def download_chunks(file_handler=None, ret_buffer=None):
            """Write to a buffer or to a file handler"""
            chunk_size = 1024 if not self._file_path else 1024 * 100
            download_size = 0
            if self._tqdm_bar is not None:
                self._tqdm_bar.desc = "Downloading {}".format(os.path.basename(self._file_path))

            for data in self._response.iter_content(chunk_size):
                download_size += len(data)
                if ret_buffer is not None:
                    ret_buffer.extend(data)
                if file_handler is not None:
                    file_handler.write(to_file_bytes(data))
                if self._tqdm_bar is not None:
                    self._tqdm_bar.update(len(data))

            return download_size

        if self._file_path:
            mkdir(os.path.dirname(self._file_path))
            with open(self._file_path, 'wb') as handle:
                dl_size = download_chunks(file_handler=handle)
        else:
            dl_size = download_chunks(ret_buffer=self._ret)

        self._response.close()
        self._finished_download = True
        return dl_size

    @property
    def encoding(self):
        return self._response.headers.get('content-encoding')

    @property
    def total_length(self):
        return self._total_length

    @property
    def data(self):
        if not self._file_path:
            return self._ret
        else:
            return

    def description(self):
        if self._tqdm_bar is not None:
            return self._tqdm_bar.desc

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
def download_file(path, response, output, **kwargs):
    file_downloader = _FileDownloaderWithProgressBar(path, response, output=output, **kwargs)
    yield file_downloader
    file_downloader.pb_close()
    if output and not output.is_terminal:
        output.writeln("\n")


@contextmanager
def open_file_list(files_list, output, **kwargs):
    list_wrapped = _FileListIteratorWithProgressBar(files_list, output=output, **kwargs)
    yield list_wrapped
    list_wrapped.pb_close()
    if output and not output.is_terminal:
        output.writeln("\n")
