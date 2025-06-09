import os
import subprocess
import httpx
import sys
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

# 공통 코드 실행 함수
def execute_code(code, input_data, lang):
    base_dir = '/home/ec2-user/DebugVisual_Spike/server/code'
    flask_dir = '/usr/src/app/code'
    os.makedirs(base_dir, exist_ok=True)

    file_map = {
        'c': ('main.c', 'c-compiler'),
        'python': ('main.py', 'python-compiler'),
        'java': ('Main.java', 'java-compiler'),
    }

    if lang not in file_map:
        return None, f"❌ 지원하지 않는 언어입니다: {lang}"

    filename, image = file_map[lang]
    code_path = os.path.join(flask_dir, filename)
    input_path = os.path.join(flask_dir, 'input.txt')

    with open(code_path, 'w') as f:
        f.write(code)

    with open(input_path, 'w') as f:
        f.write(input_data)

    if lang == 'python':
        docker_cmd = [
            'docker', 'run', '--rm',
            '-v', f'{base_dir}:/code',
            '-w', '/code', image,
            'python', filename
        ]
    elif lang == 'java':
        docker_cmd = [
            'docker', 'run', '--rm',
            '-v', f'{base_dir}:/code',
            '-w', '/code', image,
            'sh', '-c', 'javac Main.java && java Main'
        ]
    elif lang == 'c':
        docker_cmd = [
            'docker', 'run', '--rm',
            '-v', f'{base_dir}:/code',
            '-w', '/code', image,
            'sh', '-c', 'gcc main.c -o program && ./program'
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
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "",
            "exitCode": -1,
            "success": False,
            "error": "⏰ 실행 시간이 초과되었습니다."
        }, None

    return result, None

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
        print("✅ JSON 파싱 성공:", data, flush=True)
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
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "이 코드의 출력결과를 알려줘"},
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
