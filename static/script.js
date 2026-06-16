document.getElementById('translate-btn').addEventListener('click', async () => {
    const sourceText = document.getElementById('source-text').value;
    const sourceLang = document.getElementById('source-lang').value;
    const targetLang = document.getElementById('target-lang').value;
    const tone = document.getElementById('tone').value;
    const translatedText = document.getElementById('translated-text');

    if (!sourceText) {
        alert('请输入要翻译的文本');
        return;
    }

    translatedText.innerHTML = '<div class="loading">翻译中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></div>';

    try {
        const response = await fetch('/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: sourceText,
                source_lang: sourceLang,
                target_lang: targetLang,
                tone: tone
            })
        });

        // 请求入口参数错误等，后端会以 JSON（非 SSE）返回
        if (!response.ok) {
            let msg = `翻译请求失败（HTTP ${response.status}）`;
            try {
                const errData = await response.json();
                if (errData && errData.error) msg = errData.error;
            } catch (_) { /* 忽略解析失败，沿用默认提示 */ }
            throw new Error(msg);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        translatedText.innerHTML = '';

        let buffer = '';
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // 按 SSE 规范以 \n\n 分帧，处理半包/粘包
            buffer += decoder.decode(value, { stream: true });
            const frames = buffer.split('\n\n');
            // 最后一段可能不完整，留到下次拼接
            buffer = frames.pop();

            for (const frame of frames) {
                const line = frame.trim();
                if (!line.startsWith('data:')) continue;
                const payload = line.slice(5).trim();
                if (!payload) continue;

                let data;
                try {
                    data = JSON.parse(payload);
                } catch (_) {
                    // 兼容：万一收到非 JSON 的纯文本片段，直接追加
                    translatedText.innerHTML += payload;
                    continue;
                }

                if (data.error) {
                    translatedText.innerHTML = `<div class="error">${data.error}</div>`;
                    return;
                }
                if (data.delta) {
                    translatedText.innerHTML += data.delta;
                    translatedText.scrollTop = translatedText.scrollHeight;
                }
            }
        }
    } catch (error) {
        translatedText.innerHTML = `<div class="error">翻译出错: ${error.message}</div>`;
    }
});

// 回车键翻译功能
document.getElementById('source-text').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('translate-btn').click();
    }
});