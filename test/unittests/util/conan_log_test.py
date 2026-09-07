import os
import threading

from conan.internal.conan_log import LogFile, OutputTee
from conan.test.utils.test_files import temp_folder


class FakeStream:
    def __init__(self):
        self.data = ""

    def write(self, data):
        self.data += data
        return len(data)

    def flush(self):
        pass


def test_tee_writes_to_both_stream_and_log():
    log_path = os.path.join(temp_folder(), "test.log")
    log_file = LogFile(log_path)
    fake = FakeStream()
    tee = OutputTee(fake, log_file)

    tee.write("hello\n")
    log_file.close()

    assert fake.data == "hello\n"
    assert open(log_path, encoding="utf-8").read() == "hello\n"


def test_log_strips_ansi_codes():
    log_path = os.path.join(temp_folder(), "test.log")
    log_file = LogFile(log_path)
    log_file.write("\x1b[31mred text\x1b[0m\n")
    log_file.close()
    assert open(log_path, encoding="utf-8").read() == "red text\n"


def test_log_redacts_known_secrets():
    log_path = os.path.join(temp_folder(), "test.log")
    log_file = LogFile(log_path)
    log_file.secrets = ["s3cr3t"]
    log_file.write("the password is s3cr3t, really\n")
    log_file.close()
    content = open(log_path, encoding="utf-8").read()
    assert "s3cr3t" not in content
    assert "the password is ********, really" in content


def test_tee_fileno_raises_so_conan_run_knows_to_pipe():
    log_path = os.path.join(temp_folder(), "test.log")
    log_file = LogFile(log_path)
    tee = OutputTee(FakeStream(), log_file)
    try:
        tee.fileno()
        assert False, "should have raised"
    except OSError:
        pass
    log_file.close()


def test_tee_getattr_delegates_to_real_stream_not_internals():
    class StreamWithEncoding(FakeStream):
        encoding = "utf-8"

    log_path = os.path.join(temp_folder(), "test.log")
    log_file = LogFile(log_path)
    tee = OutputTee(StreamWithEncoding(), log_file)
    assert tee.encoding == "utf-8"
    try:
        tee._nonexistent_private_attr
        assert False, "internals (leading underscore) should not be delegated"
    except AttributeError:
        pass
    log_file.close()


def test_concurrent_writes_are_not_lost():
    log_path = os.path.join(temp_folder(), "test.log")
    log_file = LogFile(log_path)

    def worker(n):
        for i in range(200):
            log_file.write(f"thread{n}-line{i}\n")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log_file.close()

    lines = open(log_path, encoding="utf-8").readlines()
    assert len(lines) == 1600
