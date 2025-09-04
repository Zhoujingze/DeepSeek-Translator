from flask import Flask, render_template, request, jsonify, Response
import os
from openai import OpenAI

app = Flask(__name__)

# 从本地文件中读取提示词
def load_prompt():
    with open('prompt.txt', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    data = request.json
    text = data.get('text')
    source_lang = data.get('source_lang')
    target_lang = data.get('target_lang')
    
    client = OpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url="https://api.deepseek.com")
    
    prompt = load_prompt()
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"请将以下{source_lang}文本翻译成{target_lang}: {text}"}
    ]
    
    def generate():
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5001)  # 端口被占用可修改其他可用端口