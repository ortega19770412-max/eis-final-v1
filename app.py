import os
import json
import re
import html
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

# 1. 포트 설정 (Render 환경 대응)
PORT = int(os.environ.get("PORT", 8000))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 2. 전문적인 문장 다듬기 로직
def clean_record_text(text):
    if not text: return text
    text = re.sub(r'이 학생은|해당 학생은|본인은|저는', '', text).strip()
    sentences = text.split('. ')
    processed = []
    for sent in sentences:
        sent = sent.strip().rstrip('.')
        if not sent: continue
        # 어미 변환 (했다 -> 함 등)
        if not sent.endswith(('함', '됨', '임', '음', '기', '함.', '됨.', '임.')):
            if sent.endswith(('했다', '하였다')): sent = sent[:-2] + '함'
            elif sent.endswith(('되었다', '됐다')): sent = sent[:-2] + '됨'
            elif sent.endswith('이다'): sent = sent[:-2] + '임'
        processed.append(sent + ".")
    return " ".join(processed)

# 3. 프롬프트 및 API 호출
def build_expert_prompt(a_type, a_name, date, keywords):
    return f"""
너는 고등학교 생활기록부 작성 전문가야. 다음 정보를 바탕으로 풍부한 문장을 작성해라.

- 활동 구분: {a_type}
- 활동 일자: {date}
- 활동명: {a_name}
- 관찰 키워드: {keywords}

[작성 지침]
1. 시작은 '{a_name}({date}) 활동에서' 또는 '{a_name}({date})에 참여하여'로 시작할 것.
2. 입력된 '관찰 키워드'를 문장에 자연스럽게 녹여내어 성장이 드러나게 할 것.
3. '특히', '나아가', '이를 바탕으로' 같은 연결어를 적시에 사용할 것.
4. 모든 문장은 반드시 명사형 어미(~함, ~임, ~됨)로 끝낼 것.
"""

def call_openai_api(prompt):
    if not OPENAI_API_KEY: return "에러: API Key가 설정되지 않았습니다 (Render 환경변수를 확인하세요)."
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": "생활기록부 작성 전문가"}, {"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            res_body = json.loads(res.read().decode("utf-8"))
            return res_body['choices'][0]['message']['content'].strip()
    except Exception as e: return f"OpenAI 연결 에러: {str(e)}"

# 4. UI 템플릿
def render_template(result="", a_type="자율활동", a_name="", a_date="", a_keywords=""):
    res_safe = html.escape(result)
    sel_j = "selected" if a_type == "자율활동" else ""
    sel_z = "selected" if a_type == "진로활동" else ""
    
    return f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>생활기록부 문장 생성기</title>
    <style>
        body {{ font-family: 'Pretendard', -apple-system, sans-serif; background-color: #f1f5f9; display: flex; justify-content: center; padding: 20px; }}
        .container {{ width: 100%; max-width: 550px; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }}
        .header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 25px; }}
        .header h1 {{ font-size: 20px; color: #1e293b; margin: 0; }}
        .form-group {{ margin-bottom: 15px; }}
        label {{ display: block; font-weight: 600; margin-bottom: 5px; color: #475569; font-size: 13px; }}
        input, select, textarea {{ width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-size: 14px; }}
        .btn-submit {{ width: 100%; padding: 14px; background: #2563eb; color: white; border: none; border-radius: 6px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 10px; }}
        .result-box {{ margin-top: 20px; padding: 15px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; position: relative; }}
        .copy-btn {{ position: absolute; top: 10px; right: 10px; background: #64748b; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">🎓 <h1>생활기록부 문장 생성기</h1></div>
        <form method="post" action="/generate">
            <div class="form-group">
                <label>활동 구분</label>
                <select name="a_type">
                    <option value="자율활동" {sel_j}>자율활동</option>
                    <option value="진로활동" {sel_z}>진로활동</option>
                </select>
            </div>
            <div class="form-group">
                <label>활동 날짜</label>
                <input type="date" name="a_date" value="{a_date}" required>
            </div>
            <div class="form-group">
                <label>활동명</label>
                <input type="text" name="a_name" value="{html.escape(a_name)}" placeholder="활동 이름을 입력하세요" required>
            </div>
            <div class="form-group">
                <label>내용 키워드 (관찰 기록)</label>
                <textarea name="a_keywords" rows="4" placeholder="학생의 구체적인 행동이나 소감을 적으세요">{html.escape(a_keywords)}</textarea>
            </div>
            <button type="submit" class="btn-submit">문장 생성 및 다듬기</button>
        </form>
        {"<div class='result-box'><button class='copy-btn' onclick='copyText()'>복사</button><label>생성 결과</label><textarea id='rt' rows='6' readonly style='background:white;'>"+res_safe+"</textarea></div>" if result else ""}
    </div>
    <script>function copyText(){{var t=document.getElementById("rt");t.select();document.execCommand("copy");alert("복사되었습니다!");}}</script>
</body>
</html>
"""

# 5. 서버 핸들러
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(render_template().encode("utf-8"))

    def do_POST(self):
        if self.path == "/generate":
            content_length = int(self.headers['Content-Length'])
            post_data = parse_qs(self.rfile.read(content_length).decode('utf-8'))
            
            t = post_data.get('a_type', [''])[0]
            n = post_data.get('a_name', [''])[0]
            d = post_data.get('a_date', [''])[0]
            k = post_data.get('a_keywords', [''])[0]
            
            prompt = build_expert_prompt(t, n, d, k)
            ai_res = call_openai_api(prompt)
            final = clean_record_text(ai_res)
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_template(final, t, n, d, k).encode("utf-8"))

if __name__ == "__main__":
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, Handler) # 반드시 Handler여야 합니다.
    print(f"Server started on port {PORT}")
    httpd.serve_forever()

