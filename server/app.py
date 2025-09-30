import os
import subprocess
import httpx
import sys
import uuid
import shutil
from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수 확인
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print(f"✅ Loaded OPENAI_API_KEY: {OPENAI_API_KEY[:5]}...")  # Key 일부만 출력

# httpx Client 설정
http_client = httpx.Client(timeout=30.0)

# OpenAI Client 생성
client = OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=http_client
)

app = Flask(__name__)

@app.route('/')
def index():
    return 'DebugVisual Python Compiler Server is running!'

@app.route('/test', methods=['POST'])
def test():
    print("✅ /test 진입됨")
    return "pong"

@app.before_request
def log_request_info():
    print(f"📡 요청 URL: {request.url}")
    print(f"📡 요청 메서드: {request.method}")

@app.after_request
def cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    return response

@app.route('/echo', methods=['POST'])
def echo():
    try:
        data = request.get_json(force=True)
        print("✅ JSON 수신 성공:", data)
        return jsonify({"status": "received", "echo": data}), 200
    except Exception as e:
        print("❌ JSON 파싱 실패:", e)
        return "Invalid JSON", 400

# 공통 코드 실행 함수 (🔧 격리 디렉터리 + 정리 로직 추가)
def execute_code(code, input_data, lang):
    # 호스트 경로(왼쪽) ↔ Flask 컨테이너 경로(오른쪽) 바인드:
    # docker-compose.yml: /home/ec2-user/Zivorp_Spike/server/code:/usr/src/app/code
    base_dir = '/home/ec2-user/Zivorp_Spike/server/code'  # 호스트에서 마운트되는 경로
    flask_dir = '/usr/src/app/code'                       # Flask 컨테이너 내부 경로
    os.makedirs(flask_dir, exist_ok=True)

    file_map = {
        'c': ('main.c', 'c-compiler'),
        'python': ('main.py', 'python-compiler'),
        'java': ('Main.java', 'java-compiler'),
    }

    if lang not in file_map:
        return None, f"❌ 지원하지 않는 언어입니다: {lang}"

    # 🔹 요청별 격리 디렉터리 생성
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    job_dir_flask = os.path.join(flask_dir, job_id)  # 컨테이너 내부 경로
    os.makedirs(job_dir_flask, exist_ok=True)

    filename, image = file_map[lang]
    code_path = os.path.join(job_dir_flask, filename)
    input_path = os.path.join(job_dir_flask, 'input.txt')

    with open(code_path, 'w') as f:
        f.write(code or "")

    with open(input_path, 'w') as f:
        f.write(input_data or "")

    # 언어별 실행 커맨드 (작업 디렉터리는 /code/<job_id>)
    if lang == 'python':
        run_cmd = ['python', filename]
    elif lang == 'java':
        run_cmd = ['sh', '-c', 'javac Main.java && java Main']
    else:  # 'c'
        run_cmd = ['sh', '-c', 'gcc main.c -o program && ./program']

    # 🔹 컴파일러 컨테이너에 호스트 base_dir를 /code로 마운트하고
    #    작업디렉터리를 /code/<job_id>로 지정하여 격리 실행
    docker_cmd = [
        'docker', 'run', '--rm',
        '-v', f'{base_dir}:/code',
        '-w', f'/code/{job_id}',
        # (선택 권장 안전옵션)
        # '--network','none','--cpus','1','-m','256m','--pids-limit','128',
        image, *run_cmd
    ]
    print("🐳 Docker 실행 명령어:", ' '.join(docker_cmd))

    try:
        result = subprocess.run(
            docker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        return result, None
    except subprocess.TimeoutExpired:
        # run_code가 CompletedProcess 형태를 기대하므로 맞춰서 반환
        timeout_cp = subprocess.CompletedProcess(docker_cmd, returncode=124, stdout='', stderr='⏰ 실행 시간이 초과되었습니다.')
        return timeout_cp, None
    finally:
        # 🔹 실행 후 항상 격리 디렉터리 정리 (호스트에도 반영됨)
        shutil.rmtree(job_dir_flask, ignore_errors=True)

@app.route('/run', methods=['POST'])
def run_code():
    print("📥 /run 요청 수신됨")

    try:
        data = request.get_json(force=True)
        print("✅ JSON 파싱 성공:", data)
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}")
        return jsonify({"error": "JSON 파싱 오류", "message": str(e)}), 400

    code = data.get('code', '')
    input_data = data.get('input', '')
    lang = data.get('lang', '')

    result, error = execute_code(code, input_data, lang)

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exitCode": result.returncode,
        "success": result.returncode == 0
    }), 200 if result.returncode == 0 else 400


def safe_print(msg):
    try:
        sys.stdout.buffer.write((str(msg) + '\n').encode('utf-8'))
        sys.stdout.flush()
    except Exception as e:
        fallback_msg = str(msg).encode('utf-8', 'backslashreplace').decode('ascii', 'ignore')
        print(f"[safe_print fallback] {fallback_msg}", flush=True)

@app.route('/visualize', methods=['POST'])
def visualize_code():
    print("📥 /visualize 요청 수신됨", flush=True)

    try:
        data = request.get_json(force=True)
        print("✅ JSON 수신 성공:", data, flush=True)
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}", flush=True)
        return jsonify({"error": "JSON 파싱 오류", "message": str(e)}), 400

    code = data.get('code', '')
    input_data = data.get('input', '')
    lang = data.get('lang', '')

    result, error = execute_code(code, input_data, lang)

    if error:
        return jsonify({"error": error}), 400

    # GPT 호출용 프롬프트 구성
    gpt_prompt = f"{code}"

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 **코드 실행 시각화 JSON 생성기**입니다. 사용자가 언어(lang), 코드(code), 입력값(input)을 주면 아래 스키마에 맞춰서 **모든 연산, 비교, 대입, 스왑, 함수 호출, 반복문, 조건문, 재귀 호출, 자료구조 변화 등을 단계별로** 시각화 가능한 JSON을 **정확하고 완전하게** 생성하세요.\n\n**출력 JSON 스키마**:\n{\n  \"lang\": \"언어\",\n  \"TimeComplexity\": \"시간복잡도(Big O)\",\n  \"SpaceComplexity\": \"공간복잡도(Big O)\",\n  \"input\": \"입력값(없으면 빈 문자열)\",\n  \"variables\": [\n    { \"name\": \"변수명\", \"type\": \"자료형|array|graph|heap|linkedList|bst\", \"initialValue\": 값, \"currentValue\": 값 },\n    …\n  ],\n  \"functions\": [\n    { \"name\": \"함수명\", \"params\": [\"param1\", …], \"called\": 호출횟수 },\n    …\n  ],\n  \"steps\": [\n    {\n      \"line\": 소스코드_행번호,\n      \"description\": \"이 단계에서 일어난 일\",\n      \"changes\": [ { \"variable\": \"변수명\", \"before\": 이전값, \"after\": 이후값 }, … ],\n      \"stack\": [ { \"function\": \"함수명\", \"params\": [값들] }, … ], (선택)\n      \"loop\": { \"type\": \"for|while|do-while\", \"index\": 현재반복인덱스, \"total\": 총반복횟수 }, (선택)\n      \"condition\": { \"expression\": \"조건식\", \"result\": true|false }, (선택)\n      \"dataStructure\": { (선택)\n        \"type\": \"array|linkedList|bst|heap|graph\",\n        \"nodes\": [ \"0\", \"1\", … ] | [ { \"id\": \"0\", \"value\": 값, \"links\": [\"1\", …] }, … ],\n        \"edges\": [[\"0\",\"1\"],[\"1\",\"2\"],…], // graph 전용\n        \"adjacencyMatrix\": [[0,1],[1,0],…] // graph 전용\n      }\n    },\n    …\n  ]\n}\n\n✅ 단계별로 dataStructure 객체를 **반드시** 포함하여 자료구조 상태를 **정확히** 기록하세요.\n✅ graph의 경우 반드시 nodes, edges, adjacencyMatrix를 **모두 포함**해야 합니다.\n✅ 생략이나 … 없이 **모든 단계의 흐름과 변수/자료구조 변화**를 상세히 출력하세요.\n✅ HTML 시각화 코드와 호환되도록 구조를 유지하며, 다른 설명이나 텍스트는 **절대로 추가하지 마세요**.\n✅ **올바른 JSON만** 출력하세요."
                },
                {"role": "user", "content": gpt_prompt}
            ]
        )
        gpt_response = completion.choices[0].message.content
        safe_print(f"✅ 최종 프론트 전달용 GPT 응답: {repr(gpt_response)}")

    except Exception as e:
        print(f"❌ GPT 응답 호출 실패: {e}", flush=True)
        gpt_response = "GPT 응답 호출 실패"

    # 프론트로 응답 전송
    return jsonify({
        "stdout": result.stdout,
        "stderr": result.stderr,
        "ast": gpt_response,
        "exitCode": result.returncode,
        "success": result.returncode == 0
    }), 200 if result.returncode == 0 else 400


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5050)
