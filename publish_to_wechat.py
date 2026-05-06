import requests
import os
import json

def get_access_token():
    appid = os.getenv("WECHAT_APPID")
    secret = os.getenv("WECHAT_APPSECRET")

    # 🔥 固定IP代理（永久解决微信40164错误）
    proxies = {
        "https": "http://119.136.102.14:8080"
    }

    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    res = requests.get(url, proxies=proxies, timeout=15).json()

    return res.get("access_token", "")

def publish_article(access_token, article_data):
    proxies = {
        "https": "http://119.136.102.14:8080"
    }
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_news?access_token={access_token}"
    response = requests.post(url, json=article_data, proxies=proxies, timeout=15)
    return response.json()

def main():
    try:
        access_token = get_access_token()
        if not access_token:
            print("获取 access_token 失败")
            return

        # 你的文章内容
        article = {
            "articles": [
                {
                    "title": "每日自动发布",
                    "content": "这是通过 GitHub Actions 自动发布的内容",
                    "thumb_media_id": "",
                    "need_open_comment": 1
                }
            ]
        }

        result = publish_article(access_token, article)
        print("发布结果：", result)
    except Exception as e:
        print("错误：", e)

if __name__ == "__main__":
    main()
