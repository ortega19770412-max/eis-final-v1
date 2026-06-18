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
    # 주어 제거 및 불필요한 공백 정리
    text = re.sub(r'이 학생은|해당 학생은|본인은|저는|상기 학생은', '', text).strip()
    sentences = text.split('. ')
    processed = []
    for sent in sentences:
        sent = sent.strip().rstrip('.')
        if not sent: continue
        # 어미 변환 (했다 -> 함 등)
        if not sent.endswith(('함', '됨', '임', '음', '기', '함.', '됨.', '임.')):
            if sent.endswith(('했다', '하였다')): sent = sent[:-2] + '함'
            elif sent.endswith(('되었다', '됐다')): sent = sent[:-2] + '됨'
            elif sent.endswith(('이다', '이며')): sent = sent[:-2] + '임'
        processed.append(sent + ".")
    return " ".join(processed)

# 3. 프롬프트 및 API 호출 (400바이트 최적화: 압축과 풍성함의 조화)
def build_expert_prompt(a_type, a_name, date, keywords):
    return f"""
너는 고등학교 생활기록부 작성 전문가야. 다음 정보를 바탕으로 '400바이트(공백 포함 한글 160자 내외)'의 완성도 높은 문장을 작성해.

- 활동 구분: {a_type}
- 활동 일자: {date}
- 활동명: {a_name}
- 관찰 키워드: {keywords}

[작성 지침 - 전문성과 분량 조절]
1. 분량: 반드시 공백 포함 '한글 150~170자 이내'로 작성할 것 (400바이트 준수).
2. 표현: '돋보임', '두각을 나타냄', '심화하여 탐구함', '역량을 발휘함' 등 전문적인 미사여구를 적극 사용하여 풍성하게 느껴지게 할 것.
3. 구성: 시작은 '{a_name}({date}) 활동에서'로 하며, 활동의 구체적 노력과 성장이 유기적으로 연결되게 할 것.
4. 문체: 모든 문장은 반드시 명사형 어미(~함, ~임, ~됨)로 끝낼 것.
5. 연결어: '나아가', '이를 기반으로', '특히'를 사용하여 문장의 흐름을 고급스럽게 만들 것.
"""

def call_openai_api(prompt):
    if not OPENAI_API_KEY: return "에러: API Key를 설정하세요."
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "생활기록부 작성 전문가. 제한된 분량 내에서 가장 세련된 교육적 문장을 작성함."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7 
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            res_body = json.loads(res.read().decode("utf-8"))
            return res_body['choices'][0]['message']['content'].strip()
    except Exception as e: return f"OpenAI 에러: {str(e)}"

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
    <title>생기부 생성기 (400byte 최적화)</title>
    <style>
        body {{ font-family: 'Pretendard', sans-serif; background-color: #f1f5f9; display: flex; justify-content: center; padding: 20px; }}
        .container {{ width: 100%; max-width: 500px; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 10px 15px rgba(0,0,0,0.05); }}
        .header {{ text-align: center; margin-bottom: 20px; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; }}
        .header h1 {{ font-size: 19px; color: #1e293b; margin: 0; }}
        .form-group {{ margin-bottom: 15px; }}
        label {{ display: block; font-weight: 600; margin-bottom: 5px; color: #475569; font-size: 13px; }}
        input, select, textarea {{ width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-size: 14px; }}
        .btn-submit {{ width: 100%; padding: 14px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 15px; font-weight: 600; cursor: pointer; transition: 0.2s; }}
        .btn-submit:hover {{ background: #2563eb; }}
        .result-box {{ margin-top: 20px; padding: 15px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; position: relative; }}
        .copy-btn {{ position: absolute; top: 10px; right: 10px; background: #64748b; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; }}
        #rt {{ width: 100%; border: 1px solid #e2e8f0; border-radius: 4px; padding: 8px; font-size: 14px; line-height: 1.6; margin-top: 10px; height: 120px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">📝 <h1>진로 자율활동 문장 생성기 (400byte)</h1></div>
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
                <input type="text" name="a_name" value="{html.escape(a_name)}" placeholder="활동명 입력" required>
            </div>
            <div class="form-group">
                <label>활동 내용 (키워드)</label>
                <textarea name="a_keywords" rows="3" placeholder="핵심 행동과 성취를 입력하세요">{html.escape(a_keywords)}</textarea>
            </div>
            <button type="submit" class="btn-submit">전문 문장 생성</button>
        </form>
        {"<div class='result-box'><button class='copy-btn' onclick='copyText()'>복사</button><label>결과 (약 400byte)</label><textarea id='rt' readonly>"+res_safe+"</textarea></div>" if result else ""}
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
    httpd = HTTPServer(server_address, Handler)
    print(f"Server running on port {PORT}")
    httpd.serve_forever()
