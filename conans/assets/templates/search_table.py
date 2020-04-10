

content = """
<!DOCTYPE html>
<html lang="en">
    <head>
        <title>Conan | {{ search.reference }}</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/v/dt/dt-1.10.20/datatables.min.css"/>
        <style>
            .cell_border_right {
                border-right: 1px dashed lightgrey;
            }
            tr td {
                white-space:nowrap;
            }
        </style>
    </head>
    <body>
        <h1>{{ search.reference }}</h1>
        <p>
            Depending on your package_id_mode, any combination of settings, options and requirements
            can give you a different packageID. Take into account that yuor configuration might be
            different from the one used to generate the packages.
        </p>

        <table id="example" class="display" style="width:100%">
            <thead>
                {%- set headers = results.headers(n_rows=2) %}
                <tr>
                    {%- for category, subheaders in headers %}
                        <th rowspan="{% if subheaders|length == 1 and not subheaders[0] %}2{% else %}1{% endif %}" colspan="{{ subheaders|length }}">
                            {{ category }}
                        </th>
                    {%- endfor %}
                </tr>
                <tr>
                    {%- for category, subheaders in headers %}
                        {%- if subheaders|length != 1 or subheaders[0] != '' %}
                            {%- for subheader in subheaders %}
                                <th>{{ subheader|default(category, true) }}</th>
                            {%- endfor %}
                        {%- endif %}
                    {%- endfor %}
                </tr>
            </thead>
            <tbody>
                {%- for package in results.packages() %}
                    <tr>
                        {%- for item in package.row() %}
                            <td>{{ item if item != None else ''}}</td>
                        {%- endfor %}
                    </tr>
                {%- endfor %}
            </tbody>
            <tfoot>
                <tr>
                    {%- for header in results.headers(n_rows=1) %}
                    <th>{{ header }}</th>
                    {%- endfor %}
                </tr>
            </tfoot>
        </table>

        <script type="text/javascript" src="https://code.jquery.com/jquery-3.3.1.js"></script>
        <script type="text/javascript" src="https://cdn.datatables.net/v/dt/dt-1.10.20/datatables.min.js"></script>
        <script>
            $(document).ready(function() {
                // Setup - add a text input to each footer cell
                $('#example tfoot th').each( function () {
                    var title = $(this).text();
                    $(this).html( '<input type="text" placeholder="Search '+title+'" />' );
                });

                var table = $('#example').DataTable( {
                    "dom": "lrtip",
                    "lengthMenu": [[10, 25, 50, -1], [10, 25, 50, "All"]],
                    {# "columnDefs": [{ className: "cell_border_right", "targets": [ 2, {{ 2 + settings_len }}, {{ 2 + settings_len + options|length }} ] }]  #}
                });

                // Apply the search
                table.columns().every( function () {
                    var that = this;

                    $( 'input', this.footer() ).on( 'keyup change clear', function () {
                        if ( that.search() !== this.value ) {
                            that
                                .search( this.value )
                                .draw();
                        }
                    } );
                } );
            });
        </script>
    </body>
</html>
"""
