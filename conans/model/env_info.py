def unquote(text):
    text = text.strip()
    if len(text) > 1 and (text[0] == text[-1]) and text[0] in "'\"":
        return text[1:-1]
    return text
