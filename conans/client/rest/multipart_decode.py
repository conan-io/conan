'''
For parse Response from streaming with N files (chunked, happy memory server)
It uses multipart/mixed format
It loads all files in memory (big client computers, I don't care by now)


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


def _parse_value_in_header(header, name):
    """For parsing complex header values splitted by ;
    EX: multipart/mixed;charset=utf-8;boundary="""
    value = header.split("%s=" % name)[1]
    posend = value.find(";")
    if posend == -1:
        return value
    else:
        return value[:posend]


def decode_body(content_type, response):
    """Headers: A dict of key value
       Content: str

       returns files dict filename: body
       """
    if not content_type.startswith("multipart/mixed"):
        raise ValueError("Invalid content type")

    boundary = content_type.split("boundary=")[1]
    #charset = _parse_value_in_header(content_type, "charset")

    body_content = []
    for content in response.iter_content(2 * (1024 ** 2)):
        body_content.append(content)
    body_content = "".join(body_content)

    if not body_content.startswith("--%s" % boundary):
        raise ValueError("Invalid body")

    files = {}

    body_file_chuncks = body_content.split("--%s\n" % boundary)
    for body_file_chunk in body_file_chuncks[1:-2]:  # First is a \n, last 2 too
        headers, file_body = _parse_file_chunk(body_file_chunk)
        try:
            content_disposition = headers["content-disposition"]
        except KeyError:
            raise ValueError("Invalid file headers, Content-disposition not found")
        filename = content_disposition.split('filename="')[1][:-1]
        files[filename] = file_body

    return files


def _parse_file_chunk(body_file_chunk):
    """Parse a file chunk for getting headers and
    body for file:--AMZ90RFX875LKMFasdf09DDFF3
Content-type: image/jpeg;charset=utf-8
Content-transfer-encoding: binary
Content-disposition: attachment; filename="002.jpg"

Filecontent"""
    lines, body = body_file_chunk.split("\n\n", 1)
    file_headers = {}
    for line in lines.split("\n"):
        if line != "":
            tmp = line.split(":")
            file_headers[tmp[0].lower()] = tmp[1]

    # FIXME: Read encoding from partial header
    content_type = file_headers["content-type"]
    charset = _parse_value_in_header(content_type, "charset")
    return file_headers, body.decode(charset)
