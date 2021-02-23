
# Run the first part of the test, it will
BASEDIR=$(dirname "$0")

pushd "${BASEDIR}" || exit
rm test_underlying_sqlite3.py-locks.sqlite3
rm test_underlying_sqlite3.py-writer
rm test_underlying_sqlite3.py-reader

python test_underlying_sqlite3.py writer &
python test_underlying_sqlite3.py reader
popd || exit
