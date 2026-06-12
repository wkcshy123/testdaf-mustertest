# -*- coding: utf-8 -*-
"""
功能验证脚本 - 测试阿里云 Qwen-TTS API（德语）
"""
import os
import requests
import dashscope

# 设置 API 地址（华北2北京）
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

# 测试用API Key
API_KEY = "sk-67cf3f5a5346483cb6d77410f6b513cf"

# 测试德语文本
GERMAN_TEXT = "Guten Tag! Wie geht es Ihnen? Das ist ein Test der deutschen Sprachsynthese."

def test_tts():
    print("开始测试 Qwen-TTS API（德语）...")
    print(f"模型: qwen3-tts-flash")
    print(f"音色: Cherry")
    print(f"语言: German")
    print(f"文本: {GERMAN_TEXT}")
    print("-" * 60)
    
    try:
        response = dashscope.MultiModalConversation.call(
            model="qwen3-tts-flash",
            api_key=API_KEY,
            text=GERMAN_TEXT,
            voice="Cherry",
            language_type="German",
            stream=False
        )
        
        print(f"响应状态码: {response.status_code}")
        print(f"完整响应: {response}")
        
        if response.status_code == 200:
            audio = response.output.audio
            print(f"✓ API调用成功!")
            print(f"  音频URL: {audio.url}")
            print(f"  过期时间: {audio.expires_at}")
            
            # 下载音频
            if audio.url:
                print("\n正在下载音频...")
                dl = requests.get(audio.url)
                out_path = os.path.join(os.path.expanduser("~/Desktop"), "test_german_tts.wav")
                with open(out_path, "wb") as f:
                    f.write(dl.content)
                print(f"✓ 音频已保存: {out_path} ({len(dl.content)} bytes)")
        else:
            print(f"✗ API 调用失败: {response.code} - {response.message}")
            
    except Exception as e:
        print(f"✗ 异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tts()
