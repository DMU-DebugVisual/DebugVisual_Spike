#!/bin/bash
javac Main.java 2> compile_error.txt
if [ $? -ne 0 ]; then
  echo "컴파일 에러:"
  cat compile_error.txt
  exit 1
fi

java Main < input.txt
