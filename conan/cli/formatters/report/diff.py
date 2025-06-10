import json
import os
import base64

from jinja2 import Template

from conan.api.output import cli_out_write
from conan.cli.formatters.report.diff_html import diff_html

def _generate_json(result):
    diff_text = result["diff"]
    src_prefix = result["src_prefix"]
    dst_prefix = result["dst_prefix"]
    ret = {}
    current_filename = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            src_filename, dst_filename = _get_filenames(line, src_prefix, dst_prefix)
            current_filename = src_filename
            ret[current_filename] = [line]
        else:
            ret[current_filename].append(line)
    return ret

def _get_filenames(line, src_prefix, dst_prefix):
    """
    Extracts the source and destination filenames from a diff line.
    """
    src_index = line.find(src_prefix)
    dst_index = line.find(dst_prefix)

    if src_index == -1 or dst_index == -1:
        return None, None

    src_filename = line[src_index + len(src_prefix) - 1:dst_index - 1].strip()
    dst_filename = line[dst_index + len(dst_prefix) - 1:].strip()

    return src_filename, dst_filename

def _render_diff(content, template, template_folder, **kwargs):
    from conan import __version__
    template = Template(template, autoescape=True)
    def _safe_filename(filename):
        # Calculate base64 of the filename
        return base64.b64encode(filename.encode(), altchars=b'-_').decode()

    def _get_diff_filename(line):
        return _get_filenames(line, kwargs["src_prefix"], kwargs["dst_prefix"])[0]

    def _remove_prefixes(line):
        return line.replace(kwargs["src_prefix"][:-1], "").replace(kwargs["dst_prefix"][:-1], "")

    def _replace_cache_paths(line):
        return line.replace(kwargs["old_cache_path"], "(old)").replace(kwargs["new_cache_path"], "(new)")

    def _replace_paths(line):
        return _remove_prefixes(_replace_cache_paths(line))

    return template.render(content=content,
                           base_template_path=template_folder, version=__version__,
                           safe_filename=_safe_filename,
                           replace_paths=_replace_paths,
                           replace_cache_paths=_replace_cache_paths,
                           remove_prefixes=_remove_prefixes,
                           get_diff_filename=_get_diff_filename,
                           **kwargs)

def format_diff_html(result):
    conan_api = result["conan_api"]

    template_folder = os.path.join(conan_api.cache_folder, "templates")
    user_template = os.path.join(template_folder, "diff.html")
    template = diff_html
    if os.path.isfile(user_template):
        with open(user_template, 'r', encoding="utf-8", newline="") as handle:
            template = handle.read()

    content = _generate_json(result)

    cli_out_write(_render_diff(content, template, template_folder,
                               old_reference=result["old_export_ref"],
                               new_reference=result["new_export_ref"],
                               old_cache_path=result["old_cache_path"],
                               new_cache_path=result["new_cache_path"],
                               src_prefix=result["src_prefix"],
                               dst_prefix=result["dst_prefix"]))


def format_diff_txt(result):
    diff_text = result["diff"]
    cli_out_write(diff_text)


def format_diff_json(result):
    cli_out_write(json.dumps(_generate_json(result), indent=2))
