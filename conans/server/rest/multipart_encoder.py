'''
For generate Response in streaming with N files (chunked, happy memory server)
It uses multipart/mixed format
Example:

HTTP/1.0 200 OK
Connection: close
Date: Wed, 24 Jun 2009 23:41:40 GMT
Content-Type: multipart/mixed;boundary=AMZ90RFX875LKMFasdf09DDFF3
Client-Date: Wed, 24 Jun 2009 23:41:40 GMT
Client-Peer: 127.0.0.1:3000
Client-Response-Num: 1
MIME-Version: 1.0
Status: 200

--AMZ90RFX875LKMFasdf09DDFF3
Content-type: image/jpeg
Content-transfer-encoding: binary
Content-disposition: attachment; filename="001.jpg"

<< here goes binary data >>--AMZ90RFX875LKMFasdf09DDFF3
Content-type: image/jpeg
Content-transfer-encoding: binary
Content-disposition: attachment; filename="002.jpg"

<< here goes binary data >>--AMZ90RFX875LKMFasdf09DDFF3
--AMZ90RFX875LKMFasdf09DDFF3--

'''
import os

DEFAULT_BOUNDARY = "AMZ90RFX875LKMFasdf09DDFF3"


def get_response_chunk(response, basepath, filepaths, boundary=DEFAULT_BOUNDARY):
    """
    File is a list of filepaths
    """
    response.add_header("Content-Type", "multipart/mixed;charset=utf-8;boundary=%s" % boundary)

    for filepath in filepaths:
        yield "--%s\n" % boundary + _headers_for_file(filepath)
        for data in iter(read_file_chunked(os.path.join(basepath, filepath))):
            yield data.encode("hex")

    yield ("--%s\n--%s\n" % (boundary, boundary))


def _headers_for_file(filename):
    return '''Content-type: application/octet-stream;charset=hex
Content-transfer-encoding: binary
Content-disposition: attachment; filename="%s"

''' % filename


def read_file_chunked(filepath):
    thefile = open(filepath, "rb")
    for data in iter(read_in_chunks(thefile)):
        yield data


def read_in_chunks(file_object, chunk_size=1024):
    """Lazy function (generator) to read a file piece by piece.
    Default chunk size: 1k.
    Warn: Python file.read is returning \n instead of EOF,
    we read two chunks before return to know if EOF is reached
    so used memory is chunk_size*2"""
    while True:
        buf1 = file_object.read(chunk_size)
        if not buf1:
            break

#        buf2 = file_object.read(chunk_size)
#         if not buf2:  # Last buf1 has and ending \n that is a EOF
#             buf1 = buf1[:-1] if buf1[-1] == "\n" else buf1
#             yield buf1
#         else:
        yield buf1
        # yield buf2


if __name__ == "__main__":
    # MAKE A TEST WITH THIS! I WOULD NOT LIKE TO CHECK THAT file.read bug with
    # EOF IS NOT HAPPENING IN OTHER SO
    paths = ["/home/laso/.conans/openssl/2.0.1/lasote/testing/reg/cosa2.txt",
             "/home/laso/.conans/openssl/2.0.1/lasote/testing/reg/conandigest.txt"]
    allt = ""
    for tmp in iter(get_response_chunk(paths)):
        allt += tmp

    print(allt)
