#!/bin/bash

echo "▶ Python 실행 시작"

echo "📜 [main.py]"
cat main.py || echo "⚠️ main.py 없음"
echo

echo "📜 [input.txt]"
cat input.txt || echo "⚠️ input.txt 없음"
echo

python3 main.py < input.txt > output.txt 2> runtime_error.txt
status=$?

echo "📄 [output.txt]"
cat output.txt || echo "⚠️ output.txt 없음"
echo

echo "❌ [runtime_error.txt]"
cat runtime_error.txt || echo "⚠️ runtime_error.txt 없음"
echo

# 성공했든 실패했든 결과 확인 후에 파일 삭제
rm -f output.txt runtime_error.txt

exit $status