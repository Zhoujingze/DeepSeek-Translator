document.getElementById('translate-btn').addEventListener('click', async () => {
    const sourceText = document.getElementById('source-text').value;
    const sourceLang = document.getElementById('source-lang').value;
    const targetLang = document.getElementById('target-lang').value;
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
                target_lang: targetLang
            })
        });
        
        if (!response.ok) {
            throw new Error('翻译请求失败');
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        translatedText.innerHTML = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            translatedText.innerHTML += chunk;
            translatedText.scrollTop = translatedText.scrollHeight;
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