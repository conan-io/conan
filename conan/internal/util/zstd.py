import os
import tarfile

from conan.errors import ConanException

try:
    import zstandard
    zstandard_exception = None
except ImportError as e:
    zstandard_exception = e


def raise_if_zstandard_not_present(operation):
    if zstandard_exception:
        raise ConanException(
            f"zstandard {operation} was requested, but the required package is not present. "
            f"Please install it using 'pip install zstandard' and try again. "
            f"Exception details: {zstandard_exception}")


def tar_zst_compress(tar_path, files, compresslevel=None):
    raise_if_zstandard_not_present("compression")

    with open(tar_path, "wb") as tarfile_obj:
        # Only provide level if it was overridden by config.
        zstd_kwargs = {}
        if compresslevel is not None:
            zstd_kwargs["level"] = compresslevel

        dctx = zstandard.ZstdCompressor(write_checksum=True, threads=-1, **zstd_kwargs)

        # Create a zstd stream writer so tarfile writes uncompressed data to
        # the zstd stream writer, which in turn writes compressed data to the
        # output tar.zst file.
        with dctx.stream_writer(tarfile_obj) as stream_writer:
            # The choice of bufsize=32768 comes from profiling compression at various
            # values and finding that bufsize value consistently performs well.
            # The variance in compression times at bufsize<=64KB is small. It is only
            # when bufsize>=128KB that compression times start increasing.
            with tarfile.open(mode="w|", fileobj=stream_writer, bufsize=32768,
                              format=tarfile.PAX_FORMAT) as tar:
                current_frame_bytes = 0
                for filename, abs_path in sorted(files.items()):
                    tar.add(abs_path, filename, recursive=False)

                    # Flush the current frame if it has reached a large enough size.
                    # There is no required size, but 128MB is a good starting point
                    # because it allows for faster random access to the file.
                    current_frame_bytes += os.path.getsize(abs_path)
                    if current_frame_bytes >= 134217728:
                        stream_writer.flush(zstandard.FLUSH_FRAME)
                        current_frame_bytes = 0
