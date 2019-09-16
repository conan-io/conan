import os
from contextlib import contextmanager

from tqdm import tqdm

from conans.util.files import mkdir, save_append, to_file_bytes

TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'


class FileReaderWithProgressBar(object):
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
        self._total_size = self.tell()
        self._tqdm_bar = tqdm(total=self._total_size, desc=desc, file=output, **pb_kwargs)
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

    def __len__(self):
        return self._total_size

    def __iter__(self):
        chunk_size = 1024
        chunk = self._fileobj.read(chunk_size)
        if chunk:
            yield chunk
        else:
            return

    def pb_close(self):
        self._tqdm_bar.close()


class _FileDownloaderWithProgressBar(object):
    tqdm_defaults = {'unit': 'B',
                     'unit_scale': True,
                     'unit_divisor': 1024,
                     'dynamic_ncols': False,
                     'leave': True,
                     'ascii': True}

    def __init__(self, file_path, response, output, desc=None):
        self._tqdm_bar = None
        self._ret = bytearray()
        self._response = response
        self._file_path = file_path
        self._total_length = response.headers.get('content-length')
        self._finished_download = False
        pb_kwargs = self.tqdm_defaults.copy()
        if self._total_length is None:  # no content length header
            if not file_path:
                self._ret += self._response.content
            else:
                self._total_length = len(response.content)
                self.finished_download = True
        else:
            self._total_length = int(self._total_length)

        if output:
            if not output.is_terminal and self._file_path:
                output = _NoTerminalOutput(output)
                pb_kwargs['mininterval'] = TIMEOUT_BEAT_SECONDS
            elif self._file_path:
                self._tqdm_bar = tqdm(total=self._total_length,
                                      desc="Downloading {}".format(os.path.basename(file_path)),
                                      file=output, **pb_kwargs)

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


class _NoTerminalOutput(object):
    """ Helper class: Replace every message sent to it with a fixed one """

    def __init__(self, output):
        self._output = output

    def write(self, *args, **kwargs):
        self._output.write(TIMEOUT_BEAT_CHARACTER)

    def flush(self):
        self._output.flush()


class _FileListIteratorWithProgressBar(object):

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
    if not output.is_terminal:
        output.writeln("\n")
