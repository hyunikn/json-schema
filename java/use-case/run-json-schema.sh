#!/bin/bash

JSON_SCHEMA_HOME=../..
EXAMPLES=$JSON_SCHEMA_HOME/examples

#python3 $JSON_SCHEMA_HOME/main-for-java.py test . ./src/main/java com.mycompany.app.c \
python3 $JSON_SCHEMA_HOME/main-for-java.py test . ./src/main/java com.mycompany.app.c -i com.mycompany.app.i \
$EXAMPLES/ints.schema.json $EXAMPLES/uints.schema.json $EXAMPLES/test01.schema.json $EXAMPLES/test02.schema.json
