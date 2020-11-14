#!/bin/bash

python3 main-for-java.py ints java/test-out java/test-out a.b.c -i a.b.i \
            examples/ints.schema.json examples/uints.schema.json
python3 main-for-java.py test01 java/test-out java/test-out a.b.c -i a.b.i examples/test01.schema.json
python3 main-for-java.py test02 java/test-out java/test-out a.b.c -i a.b.i examples/test02.schema.json
