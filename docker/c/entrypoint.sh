#!/bin/bash

echo "▶ C 실행 시작"

echo "📜 [main.c]"
cat main.c || echo "⚠️ main.c 없음"
echo

echo "📜 [input.txt]"
cat input.txt || echo "⚠️ input.txt 없음"
echo

gcc main.c -o program 2> compile_error.txt
if [ $? -ne 0 ]; then
  echo "❌ 컴파일 에러:"
  cat compile_error.txt || echo "⚠️ compile_error.txt 없음"
  rm -f compile_error.txt
  exit 1
fi

./program < input.txt > output.txt 2> runtime_error.txt
status=$?

echo "📄 [output.txt]"
cat output.txt || echo "⚠️ output.txt 없음"
echo

echo "❌ [runtime_error.txt]"
cat runtime_error.txt || echo "⚠️ runtime_error.txt 없음"
echo

rm -f program output.txt compile_error.txt runtime_error.txt
exit $status