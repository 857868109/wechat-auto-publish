import requests
import os
import json

def get_access_token():
    appid = os.getenv("WECHAT_APPID")
    secret = os.getenv("WECHAT_APPSECRET")

    if not appid or not secret:
        print("❌ 错误：未配置 WECHAT_APPID 或 WECHAT_APPSECRET")
        return None

    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
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
    token = get_access_token()
    if not token:
        return

    result = create_draft(token)
    if result.get("errcode") == 0:
        print("✅ 草稿创建成功！去公众号后台查看")
    else:
        print("❌ 失败：", result)

if __name__ == "__main__":
    main()
