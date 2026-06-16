from flask import Flask, render_template, request, Response
import json

from dotenv import load_dotenv

# API Key 安全隔离：从 .env 加载环境变量（必须在导入 llm_client 之前执行，
# 以保证封装层初始化时能读到环境变量）
load_dotenv()

# 路由层只依赖封装层的高层接口，不再直接 import openai SDK，
# 体现"SDK 二次封装"带来的解耦。
from llm_client import get_client, LLMClientError

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/translate', methods=['POST'])
def translate():
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    source_lang = data.get('source_lang', '中文')
    target_lang = data.get('target_lang', '英文')
    tone = data.get('tone', 'default')

    # 请求参数校验：规范化请求入口
    if not text:
        return Response(
            json.dumps({'error': '请输入要翻译的文本'}, ensure_ascii=False),
            status=400,
            mimetype='application/json',
        )
    if source_lang == target_lang:
        return Response(
            json.dumps({'error': '源语言与目标语言不能相同'}, ensure_ascii=False),
            status=400,
            mimetype='application/json',
        )

    # 获取二次封装的大模型客户端（单例）
    try:
        client = get_client()
    except LLMClientError as e:
        return Response(
            json.dumps({'error': e.message}, ensure_ascii=False),
            status=e.status_code,
            mimetype='application/json',
        )

    def generate():
        # 调用封装层的流式接口；封装层已把成功片段和异常统一成 dict
        # 路由层再用标准 SSE 数据帧（data: {json}\n\n）下发，前端按行解析即可
        for piece in client.translate_stream(text, source_lang, target_lang, tone):
            yield f"data: {json.dumps(piece, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True, port=5001)  # 端口被占用可修改其他可用端口