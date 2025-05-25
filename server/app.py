import os
import subprocess
from flask import Flask, request, jsonify

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

@app.route('/run', methods=['POST'])
def run_code():
    print("📥 /run 요청 수신됨", flush=True)

    try:
        print("🧪 JSON 파싱 시도 전:", request.data, flush=True)
        data = request.get_json(force=True)
        print("✅ JSON 파싱 성공:", data, flush=True)
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}", flush=True)
        return jsonify({"error": "JSON 파싱 오류", "message": str(e)}), 400

    code = data.get('code', '')
    input_data = data.get('input', '')
    lang = data.get('lang', 'c')
    print(f"🔠 언어: {lang}, 코드 일부: {repr(code[:30])}", flush=True)

    base_dir = '/home/ec2-user/DebugVisual_Spike/server/code'
    os.makedirs(base_dir, exist_ok=True)

    file_map = {
        'c': ('main.c', 'c-compiler'),
        'python': ('main.py', 'python-compiler'),
        'java': ('Main.java', 'java-compiler'),
    }

    if lang not in file_map:
        return jsonify({"error": f"❌ 지원하지 않는 언어입니다: {lang}"}), 400

    filename, image = file_map[lang]
    code_path = os.path.join(base_dir, filename)
    input_path = os.path.join(base_dir, 'input.txt')

    try:
        with open(code_path, 'w') as f:
            f.write(code)
        with open(input_path, 'w') as f:
            f.write(input_data)
        print("✅ 코드 & 입력 파일 저장 성공", flush=True)

        docker_cmd = [
            'docker', 'run', '--rm',
            '-v', f'{base_dir}:/usr/src/app',
            image
        ]
        print("🐳 Docker 실행 명령어:", ' '.join(docker_cmd), flush=True)

        print("📦 Docker 실행 직전", flush=True)
        result = subprocess.run(
            docker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )

        print("✅ Docker 실행 완료", flush=True)
        print("🟢 STDOUT:", result.stdout, flush=True)
        print("🔴 STDERR:", result.stderr, flush=True)
        print("🔁 반환 코드:", result.returncode, flush=True)

        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exitCode": result.returncode,
            "success": result.returncode == 0
        }), 200 if result.returncode == 0 else 400

    except subprocess.TimeoutExpired:
        print("⏰ Docker 실행 시간 초과", flush=True)
        return jsonify({"error": "⏰ 실행 시간이 초과되었습니다."}), 408

    except Exception as e:
        print(f"❌ [Flask] 예외 발생: {e}", flush=True)
        return jsonify({"error": "🚨 실행 중 예외 발생", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5050)