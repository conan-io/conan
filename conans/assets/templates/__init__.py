
from jinja2 import DictLoader

import conans.assets.templates.search_table_html

SEARCH_TABLE_HTML = 'output/search_table.html'


dict_loader = DictLoader({
    SEARCH_TABLE_HTML: search_table_html.content,
})
