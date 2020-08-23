import os
from contextlib import contextmanager
import time

from tqdm import tqdm

from conans.client.output import ConanOutput

TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'
LEFT_JUSTIFY_DESC = 28
LEFT_JUSTIFY_MESSAGE = 90


def left_justify_message(msg):
    return msg.ljust(LEFT_JUSTIFY_MESSAGE)


def left_justify_description(msg):
    return msg.ljust(LEFT_JUSTIFY_DESC)


class ProgressOutput(ConanOutput):
    def __init__(self, output):
        super(ProgressOutput, self).__init__(output._stream, output._stream_err, output._color)

    def _write(self, data, newline=False):
        end = "\n" if newline else ""
        tqdm.write(str(data), file=self._stream, end=end)

    def _write_err(self, data, newline=False):
        end = "\n" if newline else ""
        tqdm.write(str(data), file=self._stream_err, end=end)


class Progress(object):
    def __init__(self, length, output, description, post_description=None):
        self._tqdm_bar = None
        self._total_length = length
        self._output = output
        self._processed_size = 0
        self._description = description
        self._post_description = "{} completed".format(
            self._description) if not post_description else post_description
        self._last_time = time.time()
        if self._output and self._output.is_terminal and self._description:
            self._tqdm_bar = tqdm(total=self._total_length,
                                  desc=left_justify_description(self._description),
                                  file=self._output, unit="B", leave=False, dynamic_ncols=False,
                                  ascii=True, unit_scale=True, unit_divisor=1024)

    def initial_value(self, value):
        self._processed_size = value
        self._pb_update(value)

    def _pb_update(self, chunk_size):
        if self._tqdm_bar is not None:
            self._tqdm_bar.update(chunk_size)
        elif self._output and time.time() - self._last_time > TIMEOUT_BEAT_SECONDS:
            self._last_time = time.time()
            self._output.write(TIMEOUT_BEAT_CHARACTER)

    def update(self, chunks):
        for chunk in chunks:
            yield chunk
            data_size = len(chunk)
            self._processed_size += data_size
            self._pb_update(data_size)

        if self._total_length > self._processed_size:
            self._pb_update(self._total_length - self._processed_size)

        self.pb_close()

    def pb_close(self):
        if self._tqdm_bar is not None:
            self._tqdm_bar.close()
            msg = "\r{} [{:1.2f}k]".format(self._post_description, self._processed_size / 1024.0)
            tqdm.write(left_justify_message(msg), file=self._output, end="\n")


class FileWrapper(Progress):
    def __init__(self, fileobj, output, description, post_description=None):
        self._fileobj = fileobj
        self.seek(0, os.SEEK_END)
        super(FileWrapper, self).__init__(self.tell(), output, description, post_description)
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
        self._pb_update(self.tell() - prev)
        return ret


class ListWrapper(object):
    def __init__(self, files_list, output, description, post_description=None):
        self._files_list = files_list
        self._total_length = len(self._files_list)
        self._iterator = iter(self._files_list)
        self._last_progress = None
        self._i_file = 0
        self._output = output
        self._description = description
        self._post_description = "{} completed".format(
            self._description) if not post_description else post_description
        self._last_time = time.time()
        if self._output and self._output.is_terminal:
            self._tqdm_bar = tqdm(total=len(files_list),
                                  desc=left_justify_description(self._description),
                                  file=self._output, unit="files ", leave=False, dynamic_ncols=False,
                                  ascii=True)

    def update(self):
        self._i_file = self._i_file + 1
        if self._output and self._output.is_terminal:
            self._tqdm_bar.update()
        elif self._output and time.time() - self._last_time > TIMEOUT_BEAT_SECONDS:
            self._last_time = time.time()
            self._output.write(TIMEOUT_BEAT_CHARACTER)

    def pb_close(self):
        if self._output and self._output.is_terminal:
            self._tqdm_bar.close()
            msg = "\r{} [{} files]".format(self._post_description, self._total_length)
            tqdm.write(left_justify_message(msg), file=self._output, end="\n")

    def __iter__(self):
        return self

    def __next__(self):
        val = next(self._iterator)
        self.update()
        return val

    def next(self):
        return self.__next__()


@contextmanager
def open_binary(path, output, description):
    with open(path, mode='rb') as file_handler:
        file_wrapped = FileWrapper(file_handler, output, description)
        yield file_wrapped
        file_wrapped.pb_close()


@contextmanager
def iterate_list_with_progress(files_list, output, description):
    list_wrapped = ListWrapper(files_list, output, description)
    yield list_wrapped
    list_wrapped.pb_close()
