content = """
<!DOCTYPE html>
<html lang="en">
    <head>
        <title>Conan | {{ search.reference }}</title>
        <link rel="stylesheet" type="text/css" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css"/>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.21/css/dataTables.bootstrap.min.css"/>
        <style>
            tr td {
                white-space:nowrap;
            }
        </style>
    </head>
    <body>
        <div class="container-fluid">
        <h1>{{ search.reference }}</h1>
        <div class="info">
            <p>
                Depending on your package_id_mode, any combination of settings, options and requirements
                can give you a different packageID. Take into account that your configuration might be
                different from the one used to generate the packages.
            </p>
        </div>

        <table id="results" class="table table-striped table-bordered" style="width:100%">
            <thead>
                {%- set headers = results.get_headers(keys=['remote', 'package_id', 'outdated']) %}
                {%- set headers2rows = headers.row(n_rows=2) %}
                <tr>
                    {%- for category, subheaders in headers2rows %}
                        <th class="text-center" rowspan="{% if subheaders|length == 1 and not subheaders[0] %}2{% else %}1{% endif %}" colspan="{{ subheaders|length }}">
                            {{ category }}
                        </th>
                    {%- endfor %}
                </tr>
                <tr>
                    {%- for category, subheaders in headers2rows %}
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
                        {%- for item in package.row(headers) %}
                            <td>{{ item if item != None else ''}}</td>
                        {%- endfor %}
                    </tr>
                {%- endfor %}
            </tbody>
            <tfoot>
                <tr>
                    {%- for header in headers.row(n_rows=1) %}
                    <th>{{ header }}</th>
                    {%- endfor %}
                </tr>
            </tfoot>
        </table>

        <script type="text/javascript" src="https://code.jquery.com/jquery-3.3.1.js"></script>
        <script type="text/javascript" src="https://cdn.datatables.net/v/dt/dt-1.10.20/datatables.min.js"></script>
        <script type="text/javascript" src="https://cdn.datatables.net/1.10.21/js/dataTables.bootstrap.min.js"></script>
        <script>
            $(document).ready(function() {
                // Setup - add a text input to each footer cell
                $('#results tfoot th').each( function () {
                    var title = $(this).text();
                    $(this).html( '<input type="text" class="form-control filter-input" placeholder="Filter '+title+'" style="width:100%"/>' );
                });

                var table = $('#results').DataTable( {
                    "dom": "lrtip",
                    "lengthMenu": [[10, 25, 50, -1], [10, 25, 50, "All"]],
                    "pageLength": 10,
                    "columnDefs": [
                        { className: "cell_border_right", "targets": [ {{ headers.keys|length + headers.settings|length -1 }}, {{ headers.keys|length + headers.settings|length + headers.options|length -1 }}  ] },
                        { className: "cell_border_right monospaced", "targets": [{{ headers.keys|length -1 }}, ]}
                    ]
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
    </div>
    </body>
    <footer>
        <div class="container-fluid">
            <div class="info">
                <p>
                      Conan <b>v{{ version  }}</b> <script>document.write(new Date().getFullYear())</script> JFrog LTD. <a>https://conan.io</a>
                </p>
            </div>
        </div>
    </footer>
</html>
"""
