import os
import subprocess
import sys
import httpx
from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import shlex

# .env 로드
load_dotenv()

# ==== OpenAI 클라이언트 (키 없으면 비활성) ====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    print("🔐 OPENAI_API_KEY loaded")
else:
    print("⚠️ OPENAI_API_KEY not set; OpenAI features disabled")

http_client = httpx.Client(timeout=30.0)
client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client) if OPENAI_API_KEY else None

app = Flask(__name__)

# 실행 작업 디렉터리
TMP_DIR = Path("/usr/src/app/code")
TMP_DIR.mkdir(parents=True, exist_ok=True)

MAX_TIME = int(os.getenv("EXEC_TIMEOUT_SEC", "10"))  # 실행 타임아웃
PY_BIN = ["python", "-X", "utf8"]                    # 파이썬 실행 커맨드

# ========== 공통 유틸 ==========
def run_proc(cmd, *, cwd=None, stdin_data="", timeout=MAX_TIME):
    """명령 실행 유틸. stdout/stderr/returncode 반환."""
    try:
        print(f"▶️ run: {shlex.join(cmd)}  (cwd={cwd})")
        p = subprocess.run(
            cmd,
            input=(stdin_data or "").encode("utf-8"),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return p.stdout.decode("utf-8", "ignore"), p.stderr.decode("utf-8", "ignore"), p.returncode, None
    except subprocess.TimeoutExpired:
        return "", "", -1, "⏰ 실행 시간이 초과되었습니다."

def safe_print(msg):
    try:
        sys.stdout.buffer.write((str(msg) + "\n").encode("utf-8"))
        sys.stdout.flush()
    except Exception:
        fallback_msg = str(msg).encode("utf-8", "backslashreplace").decode("ascii", "ignore")
        print(f"[safe_print fallback] {fallback_msg}", flush=True)

def normalize_lang(lang: str) -> str:
    if not lang:
        return "python"
    l = lang.lower()
    if l in {"py", "python3"}:
        return "python"
    if l.startswith("java"):
        return "java"
    if l in {"c"}:
        return "c"
    return l

# ========== 웹 훅/헬스/CORS ==========
@app.before_request
def log_request_info():
    print(f"📡 요청 URL: {request.url}")
    print(f"📡 요청 메서드: {request.method}")

@app.after_request
def cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp

@app.get("/")
def index():
    return "DebugVisual Python Compiler Server is running!"

@app.get("/healthz")
def healthz():
    return "OK", 200

@app.post("/test")
def test():
    print("✅ /test 진입됨")
    return "pong"

@app.post("/echo")
def echo():
    try:
        data = request.get_json(force=True)
        print("✅ JSON 수신 성공:", data)
        return jsonify({"status": "received", "echo": data}), 200
    except Exception as e:
        print("❌ JSON 파싱 실패:", e)
        return "Invalid JSON", 400

# ========== 언어별 실행 ==========
def exec_python(code: str, stdin_data: str):
    src = TMP_DIR / "main.py"
    src.write_text(code or "", encoding="utf-8")
    return run_proc([*PY_BIN, str(src)], cwd=TMP_DIR, stdin_data=stdin_data)

def exec_c(code: str, stdin_data: str):
    src = TMP_DIR / "main.c"
    bin_path = TMP_DIR / "program"
    src.write_text(code or "", encoding="utf-8")

    # 컴파일
    out, err, rc, to = run_proc(["gcc", "-O2", "-std=c11", str(src), "-o", str(bin_path)], cwd=TMP_DIR)
    if to:  # 타임아웃
        return "", to, -1, to
    if rc != 0:
        return out, err, rc, None

    # 실행
    return run_proc([str(bin_path)], cwd=TMP_DIR, stdin_data=stdin_data)

def exec_java(code: str, stdin_data: str):
    # 클래스명은 Main으로 고정
    src = TMP_DIR / "Main.java"
    src.write_text(code or "", encoding="utf-8")

    # 컴파일
    out, err, rc, to = run_proc(["javac", str(src)], cwd=TMP_DIR)
    if to:
        return "", to, -1, to
    if rc != 0:
        return out, err, rc, None

    # 실행 (CLASSPATH = TMP_DIR)
    return run_proc(["java", "-cp", str(TMP_DIR), "Main"], cwd=TMP_DIR, stdin_data=stdin_data)

def execute_code(code: str, input_data: str, lang: str):
    lang = normalize_lang(lang)
    if lang == "python":
        return exec_python(code, input_data)
    if lang == "c":
        return exec_c(code, input_data)
    if lang == "java":
        return exec_java(code, input_data)
    return "", f"❌ 지원하지 않는 언어입니다: {lang}", 1, None

# ========== /run ==========
@app.route("/run", methods=["POST", "OPTIONS"])
def run_code():
    if request.method == "OPTIONS":
        return jsonify({"ok": True}), 200

    print("📥 /run 요청 수신됨")
    try:
        data = request.get_json(force=True)
        print("✅ JSON 파싱 성공:", data)
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}")
        return jsonify({"error": "JSON 파싱 오류", "message": str(e)}), 400

    # lang / language 둘 다 지원, 기본값 python
    lang = data.get("lang") or data.get("language") or "python"
    code = data.get("code", "")
    stdin_data = data.get("input", "") or data.get("stdin", "")

    out, err, rc, timeout_msg = execute_code(code, stdin_data, lang)
    if timeout_msg:
        return jsonify({"stdout": out, "stderr": timeout_msg, "exitCode": -1, "success": False}), 400

    return jsonify({
        "stdout": out,
        "stderr": err,
        "exitCode": rc,
        "success": rc == 0
    }), 200 if rc == 0 else 400

# ========== /visualize ==========
@app.post("/visualize")
def visualize_code():
    print("📥 /visualize 요청 수신됨", flush=True)

    try:
        data = request.get_json(force=True)
        print("✅ JSON 파싱 성공:", data, flush=True)
    except Exception as e:
        print(f"❌ JSON 파싱 실패: {e}", flush=True)
        return jsonify({"error": "JSON 파싱 오류", "message": str(e)}), 400

    lang = data.get("lang") or data.get("language") or "python"
    code = data.get("code", "")
    stdin_data = data.get("input", "") or data.get("stdin", "")

    out, err, rc, timeout_msg = execute_code(code, stdin_data, lang)
    if timeout_msg:
        return jsonify({"error": timeout_msg}), 400
    # GPT 호출
    gpt_response = None
    if client is None:
        print("⚠️ OpenAI 비활성: OPENAI_API_KEY 미설정", flush=True)
        gpt_response = "OpenAI disabled"
    else:
        gpt_prompt = f"{code}"
        try:
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system",
                     "content": "사용자 코드에 대한 단계별 시각화 JSON만 출력하세요."},
                    {"role": "user", "content": gpt_prompt},
                ],
            )
            gpt_response = completion.choices[0].message.content
            safe_print(f"✅ 최종 프론트 전달용 GPT 응답: {repr(gpt_response)}")
        except Exception as e:
            print(f"❌ GPT 응답 호출 실패: {e}", flush=True)
            gpt_response = "GPT 응답 호출 실패"

    return jsonify({
        "stdout": out,
        "stderr": err,
        "ast": gpt_response,
        "exitCode": rc,
        "success": rc == 0
    }), 200 if rc == 0 else 400

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    app.run(host="0.0.0.0", port=port)
