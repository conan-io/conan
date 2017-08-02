#!/bin/sh

# Run server on port 9300 with 4 workers and a timeout of 5 minutes (300 seconds)
gunicorn -b 0.0.0.0:9300 -w 4 -t 300 conans.server.server_launcher:app
