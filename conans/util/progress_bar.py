
import os
import tqdm


class FileObjectProgress:
    def __init__(self, fileobj, desc=None):
        self._fileobj = fileobj
        self._fileobj.seek(0, os.SEEK_END)
        self._pb = tqdm.tqdm(total=self.tell(), desc=desc,
                             unit='B', unit_scale=True, unit_divisor=1024)
        self._fileobj.seek(0)

    def tell(self):
        return self._fileobj.tell()

    def read(self, size):
        prev = self.tell()
        ret = self._fileobj.read(size)
        self._pb.update(self.tell() - prev)
        return ret
