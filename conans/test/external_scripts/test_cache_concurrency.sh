
# Run the first part of the test, it will
BASEDIR=$(dirname $0)

pushd "${BASEDIR}"
rm test_cache_concurrency.py-locks.sqlite3
rm test_cache_concurrency.py-writer
rm test_cache_concurrency.py-reader

python test_cache_concurrency.py writer &
python test_cache_concurrency.py reader
popd
