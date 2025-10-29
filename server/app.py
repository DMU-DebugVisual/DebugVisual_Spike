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
                    "content": "당신은 **코드 실행 흐름 JSON 생성기**입니다. 입력(언어 lang, 코드 code, 입력값 input)을 바탕으로, 아래 **DV-Flow v1.3 (events+analysis+meta-light, input=string)** 정규 스키마에 **정확히 부합하는 단 하나의 JSON**만 출력하세요. 설명/주석/마크다운/추가 텍스트는 절대 금지합니다. [출력은 오직 다음 4개 최상위 키만 허용] - lang, input, analysis, events  (그 외 키 금지) - input은 **프로그램의 전체 표준입력(stdin) 문자열** 하나로만 표현합니다. [정규 스키마(JSON Schema)] { "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DV-Flow v1.3 (events+analysis+meta-light, input=string)", "type": "object", "additionalProperties": false, "required": ["lang", "input", "analysis", "events"], "properties": { "lang": { "type": "string", "enum": ["c","cpp","python","js","java"] }, "input": { "type": "string" }, "analysis": { "type": "object", "additionalProperties": false, "required": ["timeComplexity", "spaceComplexity"], "properties": { "timeComplexity": { "type": "string", "pattern": "^O\\(.*\\)$" }, "spaceComplexity": { "type": "string", "pattern": "^O\\(.*\\)$" }, "opCounts": { "type": "object", "additionalProperties": { "type": "integer", "minimum": 0 } } } }, "events": { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/Event" } } }, "$defs": { "Loc": { "type": "object", "additionalProperties": false, "required": ["line"], "properties": { "file": { "type": "string" }, "line": { "type": "integer", "minimum": 1 }, "col":  { "type": "integer", "minimum": 1 } } }, "Base": { "type": "object", "additionalProperties": false, "required": ["t", "kind"], "properties": { "t":    { "type": "integer", "minimum": 1 }, "kind": { "enum": ["compare","assign","swap","call","return","loopIter","branch","ds_op","io","exception","note"] }, "loc":  { "$ref": "#/$defs/Loc" }, "viz":  { "type": "object", "additionalProperties": true } } }, "EvCompare": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"compare"} }, "required":["expr","read","result"], "properties": { "expr": { "type":"string" }, "read": { "type":"array","items":{ "type":"object","additionalProperties":false, "required":["ref","value"], "properties":{ "ref":{"type":"string"}, "value":{"type":["string","number","boolean","null","object","array"]} } }}, "result": { "type":"boolean" } } } ] }, "EvAssign": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"assign"} }, "required":["var","before","after"], "properties": { "var":    { "type":"string" }, "before": { "type":["string","number","boolean","null","object","array"] }, "after":  { "type":["string","number","boolean","null","object","array"] } } } ] }, "EvSwap": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"swap"} }, "required":["target","indices","before","after"], "properties": { "target":  { "type":"string" }, "indices": { "type":"array","minItems":2,"maxItems":2,"items":{"type":"integer","minimum":0} }, "before":  { "type":"array","minItems":2 }, "after":   { "type":"array","minItems":2 } } } ] }, "EvBranch": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"branch"} }, "required":["expr","result"], "properties": { "expr":   { "type":"string" }, "result": { "type":"boolean" } } } ] }, "EvLoopIter": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"loopIter"} }, "required":["loop"], "properties": { "loop": { "type":"object","additionalProperties":false, "required":["type","iter"], "properties":{ "type": { "enum":["for","while","do-while"] }, "iter": { "type":"integer","minimum":0 }, "total":{ "type":"integer","minimum":0 } } } } } ] }, "EvCall": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"call"} }, "required":["fn","args"], "properties": { "fn":   { "type":"string" }, "args": { "type":"array","items":{ "type":"object","additionalProperties":false, "required":["name","value"], "properties":{ "name":{"type":"string"}, "value":{"type":["string","number","boolean","null","object","array"]} } }} } } ] }, "EvReturn": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"return"} }, "required":["fn","value"], "properties": { "fn":    { "type":"string" }, "value": { "type":["string","number","boolean","null","object","array"] } } } ] }, "EvDsOp": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"ds_op"} }, "required":["target","op","args"], "properties": { "target": { "type":"string" }, "op":     { "type":"string" }, "args":   { "type":"array" } } } ] }, "EvIo": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"io"} }, "required":["dir","channel","data"], "properties": { "dir":     { "enum":["in","out"] }, "channel": { "enum":["stdin","stdout","stderr"] }, "data":    { "type":"string" } } } ] }, "EvException": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"exception"} }, "required":["type","message"], "properties": { "type":    { "type":"string" }, "message": { "type":"string" } } } ] }, "EvNote": { "allOf": [ { "$ref": "#/$defs/Base" }, { "type":"object","additionalProperties":false, "properties": { "kind":{"const":"note"} }, "required":["text"], "properties": { "text": { "type":"string" } } } ] }, "Event": { "oneOf": [ { "$ref":"#/$defs/EvCompare" }, { "$ref":"#/$defs/EvAssign" }, { "$ref":"#/$defs/EvSwap" }, { "$ref":"#/$defs/EvBranch" }, { "$ref":"#/$defs/EvLoopIter" }, { "$ref":"#/$defs/EvCall" }, { "$ref":"#/$defs/EvReturn" }, { "$ref":"#/$defs/EvDsOp" }, { "$ref":"#/$defs/EvIo" }, { "$ref":"#/$defs/EvException" }, { "$ref":"#/$defs/EvNote" } ] } } } [추가 규칙] - `events[*].t`는 **앞 이벤트보다 항상 커야** 합니다(엄격 단조증가). - 표준 JSON 값만 사용(NaN/Infinity 금지, -0 → 0 정규화)."
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
