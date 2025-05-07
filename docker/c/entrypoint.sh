#!/bin/bash
gcc main.c -o main.out 2> compile_error.txt
if [ $? -ne 0 ]; then
  echo "컴파일 에러:"
  cat compile_error.txt
  exit 1
fi

./main.out < input.txt > output.txt 2> runtime_error.txt
if [ $? -ne 0 ]; then
  echo "실행 에러:"
  cat runtime_error.txt
  exit 1
fi

cat output.txt
