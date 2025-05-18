import os
import subprocess
from flask import Flask, request

app = Flask(__name__)

@app.route('/run', methods=['POST'])
def run_code():
    print("📥 /run 요청 수신됨")

    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}")
        return 'JSON 파싱 오류', 400

    code = data.get('code', '')
    input_data = data.get('input', '')
    lang = data.get('lang', 'c')

    print(f"🔡 언어: {lang}")
    print(f"🔡 코드 샘플: {repr(code[:30])}")

    # 프로젝트 루트 (DebugVisual_Spike/)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # server/code 경로 설정
    base_dir = os.path.join(project_root, 'server', 'code')
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    file_map = {
        'c': (
            'main.c',
            'c-compiler',
            os.path.join(project_root, 'docker/c/entrypoint.sh')
        ),
        'python': (
            'main.py',
            'python-compiler',
            os.path.join(project_root, 'docker/python/entrypoint.sh')
        ),
        'java': (
            'Main.java',
            'java-compiler',
            os.path.join(project_root, 'docker/java/entrypoint.sh')
        ),
    }

    filename, image, entrypoint_host_path = file_map.get(
        lang,
        ('main.c', 'c-compiler', os.path.join(project_root, 'docker/c/entrypoint.sh'))  # 기본값
    )

    code_path = os.path.join(base_dir, filename)
    input_path = os.path.join(base_dir, 'input.txt')

    try:
        with open(code_path, 'w') as f:
            f.write(code)
        print("✅ 코드 파일 저장 성공")

        with open(input_path, 'w') as f:
            f.write(input_data)
        print("✅ 입력 파일 저장 성공")

    except Exception as e:
        print(f"❌ 파일 저장 중 오류: {e}")
        return f'파일 저장 실패: {e}', 500

    if not os.path.exists(entrypoint_host_path):
        return f'❌ entrypoint.sh 없음: {entrypoint_host_path}', 500

    try:
        docker_cmd = [
            'docker', 'run', '--rm',
            '-v', f'{base_dir}:/usr/src/app',
            '-v', f'{entrypoint_host_path}:/usr/src/app/entrypoint.sh',
            image,
            'bash', '/usr/src/app/entrypoint.sh'
        ]
        print("🐳 Docker 실행 명령:", ' '.join(docker_cmd))

        result = subprocess.run(
            docker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )

        print("✅ Docker 실행 완료")
        print("🟢 STDOUT:", result.stdout)
        print("🔴 STDERR:", result.stderr)
        print("🔁 반환 코드:", result.returncode)

        return result.stdout, 200 if result.returncode == 0 else 400

    except subprocess.TimeoutExpired:
        return '⏰ 실행 시간이 초과되었습니다.', 408

@app.after_request
def cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
