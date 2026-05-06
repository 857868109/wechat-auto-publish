import requests
import os
import json

def get_access_token():
    appid = os.getenv("WECHAT_APPID")
    secret = os.getenv("WECHAT_APPSECRET")

    # 固定IP代理（解决40164动态IP问题）
    proxies = {
        "https": "http://119.136.102.14:8080"
    }

    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    res = requests.get(url, proxies=proxies, timeout=15).json()

    return res.get("access_token", "")

def create_draft(access_token, article_data):
    """调用微信草稿箱接口，直接创建草稿"""
    proxies = {
        "https": "http://119.136.102.14:8080"
    }
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={access_token}"
    response = requests.post(url, json=article_data, proxies=proxies, timeout=15)
    return response.json()

def main():
    try:
        access_token = get_access_token()
        if not access_token:
            print("获取 access_token 失败")
            return

        # 草稿文章数据（必填字段已补全）
        draft_data = {
            "articles": [
                {
                    "title": "股市晴雨表 2026-05-05",
                    "author": "自动发布脚本",
                    "content": "<p>这是通过 GitHub Actions 自动发布的内容</p>",
                    "digest": "每日股市分析摘要",
                    "content_source_url": "",
                    "thumb_media_id": "",
                    "need_open_comment": 1,
                    "only_fans_can_comment": 0
                }
            ]
        }

        # 创建草稿
        result = create_draft(access_token, draft_data)
        print("创建草稿结果：", result)

        if result.get("errcode") == 0:
            print("✅ 草稿创建成功！请前往公众号草稿箱查看")
        else:
            print("❌ 草稿创建失败：", result.get("errmsg"))

    except Exception as e:
        print("错误：", e)

if __name__ == "__main__":
    main()
