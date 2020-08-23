from jinja2 import DictLoader

import conans.assets.templates.info_graph_dot
import conans.assets.templates.info_graph_html
import conans.assets.templates.search_table_html

SEARCH_TABLE_HTML = 'output/search_table.html'
INFO_GRAPH_DOT = 'output/info_graph.dot'
INFO_GRAPH_HTML = 'output/info_graph.html'

dict_loader = DictLoader({
    SEARCH_TABLE_HTML: search_table_html.content,
    INFO_GRAPH_DOT: info_graph_dot.content,
    INFO_GRAPH_HTML: info_graph_html.content,
})
