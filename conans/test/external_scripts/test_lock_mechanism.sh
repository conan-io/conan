
# Run the first part of the test, it will
BASEDIR=$(dirname "$0")

pushd "${BASEDIR}" || exit
rm test_lock_mechanims.py-locks.sqlite3
rm test_lock_mechanims.py-writer
rm test_lock_mechanims.py-reader

python test_lock_mechanims.py writer &
python test_lock_mechanims.py reader
popd || exit
