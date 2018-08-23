def get_mime_type(filepath):
    if filepath.endswith(".tgz"):
        mimetype = "x-gzip"
    elif filepath.endswith(".txz"):
        mimetype = "x-xz"
    else:
        mimetype = "auto"

    return mimetype