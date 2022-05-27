from collections import OrderedDict

try:
    from jwt import encode, decode, DecodeError, ExpiredSignatureError
except ImportError:  # Just for testing purposes
    def encode(fields, secret, algorithm):
        return ";".join("{}:{}".format(k, v) for k, v in fields.items())

    def decode(token, secret, algorithms):
        d = OrderedDict(t.split(":") for t in token.split(";"))
        d = {k: int(v) if v.isdigit() else v for k, v in d.items()}
        return d

    class DecodeError(Exception):
        pass

    class ExpiredSignatureError(Exception):
        pass
