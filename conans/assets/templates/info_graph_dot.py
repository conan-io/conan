
content = """\
digraph {
    {%- for src, dst in graph.edges %}
        "{{ src.label }}" -> "{{ dst.label }}"
    {%- endfor %}
}

"""
