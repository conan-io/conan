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

        <!-- Button trigger modal -->
        <span id="filterProfileButton"> |
            <button type="button" class="btn btn-link" data-toggle="modal" data-target="#filterProfile">
                Filter using profile
            </button>
        </span>

        <!-- Modal -->
        <div class="modal fade" id="filterProfile" tabindex="-1" role="dialog" aria-labelledby="filterProfileLabel" aria-hidden="true">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                        <span aria-hidden="true">&times;</span>
                        </button>
                        <h4 class="modal-title" id="filterProfileLabel">Filter results</h4>
                    </div>
                    <div class="modal-body">
                        <p>Copy and paste here the content of a Conan profile:</p>
                        <form>
                            <div class="form-group">
                                    <textarea id="filterProfileValue" class="form-control" rows="8" placeholder="[settings]&#10;os=Macos&#10;arch=x86_64&#10;compiler=apple-clang&#10;compiler.version=11.0&#10;compiler.libcxx=libc++&#10;build_type=Release"></textarea>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="apply_profile_filter()">Apply filter</button>
                    </div>
                </div>
            </div>
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

        <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js" integrity="sha384-DfXdz2htPH0lsSSs5nCTpuj/zy4C+OGpamoFVy38MVBnE+IbbVYUew+OrCXaRkfj" crossorigin="anonymous"></script>
        <script src="https://stackpath.bootstrapcdn.com/bootstrap/3.4.1/js/bootstrap.min.js" integrity="sha384-aJ21OjlMXNL5UyIl/XNwTMqvzeRMZH2w8c5cRVpzpU8Y5bApTppSuUkhZXN0VxHd" crossorigin="anonymous"></script>
        <script type="text/javascript" src="https://cdn.datatables.net/v/dt/dt-1.10.20/datatables.min.js"></script>
        <script type="text/javascript" src="https://cdn.datatables.net/1.10.21/js/dataTables.bootstrap.min.js"></script>
        <script>
            $(document).ready(function() {
                // Setup - add a text input to each footer cell
                $('#results tfoot th').each( function () {
                    var title = $(this).text();
                    var title_id = title.replace('.', '_');
                    $(this).html( '<input type="text" id="filter-input-'+title_id+'" class="form-control filter-input" placeholder="Filter '+title+'" style="width:100%"/>' );
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

                // Add filter profile to
                $("#filterProfileButton").appendTo("#results_length");
            });

            function apply_profile_filter() {
                // Parse the profile input
                var profile_txt = $("#filterProfileValue").val();
                var regex = {
                    section: /^\s*\[\s*([^\]]*)\s*\]\s*$/,
                    param: /^\s*([^=]+?)\s*=\s*(.*?)\s*$/
                };
                profile_txt.split(/[\\r\\n]+/).forEach( function(line) {
                    if(regex.param.test(line)){
                        var match = line.match(regex.param);
                        var field_id = '#filter-input-'+match[1].replace('.', '_');
                        $(field_id).val(match[2]);
                        $(field_id).keyup();
                    }
                });
                $('#filterProfile').modal('hide');
            }
        </script>
    </div>
    </body>
    <footer>
        <div class="container-fluid">
            <div class="info">
                <p>
                      Conan <b>v{{ version }}</b> <script>document.write(new Date().getFullYear())</script> JFrog LTD. <a>https://conan.io</a>
                </p>
            </div>
        </div>
    </footer>
</html>
"""
