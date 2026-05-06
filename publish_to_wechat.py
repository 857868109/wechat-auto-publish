import requests
import json

# ============ 先直接写死密钥，测试能否跑通 ============
APPID = "wxa579f1d1929ae9b6"
APPSECRET = "ca2df108070a17590779ec5c746bc6ac"

def get_access_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}"
    res = requests.get(url, timeout=15).json()
    print("获取 access_token 结果：", res)
    return res.get("access_token")

def create_draft(access_token):
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={access_token}"

    data = {
        "articles": [
            {
                "title": "股市晴雨表 2026-05-06",
                "author": "自动发布",
                "content": "<p>今日股市平稳运行</p>",
                "digest": "自动生成草稿",
                "thumb_media_id": "",
                "need_open_comment": 1,
                "only_fans_can_comment": 0
            }
        ]
    }

    response = requests.post(url, json=data, timeout=15)
    print("微信返回：", response.text)
    return response.json()

def main():
    print("=== 公众号自动发布脚本开始运行 ===")
    token = get_access_token()
    if not token:
        print("❌ 获取 access_token 失败")
        return

    result = create_draft(token)
    if result.get("errcode") == 0:
        print("✅ 草稿创建成功！去公众号后台查看")
    else:
        print("❌ 失败：", result)

if __name__ == "__main__":
    main()
