#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate
python -m carddemo.batch closefil
python -m carddemo.batch seed
python -m carddemo.batch openfil
python -m carddemo.batch posttran || test "$?" -eq 4
python -m carddemo.batch intcalc
python -m carddemo.batch tranbkp
python -m carddemo.batch combtran
python -m carddemo.batch tranidx
python -m carddemo.batch cbpaup0
python -m carddemo.batch counts
