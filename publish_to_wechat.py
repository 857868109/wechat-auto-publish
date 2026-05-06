import json
import urllib.request

def send_wecom_message():
    # 你的企业微信配置
    CORPID = "ww9fc85f8c79338abd"
    CORPSECRET = "TXlhV-99MmaHlKV-sFw-m0jwSfeghc0QXPez8aVF8P4"
    AGENTID = 1000002
    USERID = "LiangHongJiang"

    # 配置代理（用免费公开代理，可随时替换）
    proxy_handler = urllib.request.ProxyHandler({'https': 'http://101.200.127.120:3128'})
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)

    print("开始获取企业微信 Token...")

    # 1. 获取 access_token
    try:
        token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORPID}&corpsecret={CORPSECRET}"
        with urllib.request.urlopen(token_url, timeout=10) as resp:
            token_data = json.loads(resp.read())
        access_token = token_data["access_token"]
        print("✅ Token 获取成功")
    except Exception as e:
        print(f"❌ 获取Token失败: {e}")
        return

    # 2. 发送消息
    try:
        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        data = {
            "touser": USERID,
            "msgtype": "text",
            "agentid": AGENTID,
            "text": {
                "content": "✅ GitHub Actions 推送成功！\n📊 基金日报自动推送系统已上线"
            },
            "safe": 0
        }
        req = urllib.request.Request(
            send_url,
            data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        
        if result.get("errcode") == 0:
            print("✅ 消息发送成功！请打开企业微信查看")
        else:
            print(f"❌ 发送失败: {result}")

    except Exception as e:
        print(f"❌ 发送异常: {e}")

if __name__ == "__main__":
    send_wecom_message()
