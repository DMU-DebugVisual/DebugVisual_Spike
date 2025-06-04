#!/bin/bash

rm -f main.* output.txt runtime_error.txt

python3 main.py < input.txt > output.txt 2> runtime_error.txt
if [ $? -ne 0 ]; then
  echo "실행 에러:"
  [ -s runtime_error.txt ] && cat runtime_error.txt
  exit 1
fi

[ -s output.txt ] && cat output.txt