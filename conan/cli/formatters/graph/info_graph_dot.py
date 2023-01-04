
graph_info_dot = """\
digraph {
    {%- for node in graph["nodes"] %}
        {%- for dep in node["dependencies"] %}
           {%- if dep["require"]["direct"] %}
            "{{ node.ref }}" -> "{{ dep["depends"]["ref"] }}"
           {%- endif %}
        {%- endfor %}
    {%- endfor %}
}

"""
