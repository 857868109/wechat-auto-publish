import requests
import os
import json

def get_access_token():
    # 从 GitHub Secrets 读取环境变量
    appid = os.getenv("WECHAT_APPID")
    secret = os.getenv("WECHAT_APPSECRET")

    if not appid or not secret:
        print("❌ 错误：WECHAT_APPID 或 WECHAT_APPSECRET 未配置！")
        return None

    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    res = requests.get(url, timeout=15).json()
    print("获取 access_token 结果：", res)

    return res.get("access_token")

def create_draft(access_token, article_data):
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={access_token}"
    response = requests.post(url, json=article_data, timeout=15)
    print("微信返回的原始结果：", response.text)
    return response.json()

def main():
    print("=== 公众号自动发布脚本开始运行 ===")
    access_token = get_access_token()
    if not access_token:
        return

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

    result = create_draft(access_token, draft_data)
    print("=== 最终结果 ===")
    print("微信接口返回：", result)

    if result.get("errcode") == 0:
        print("✅ 草稿创建成功！请前往公众号草稿箱查看")
    else:
        print("❌ 草稿创建失败！错误码：", result.get("errcode"), "错误信息：", result.get("errmsg"))

if __name__ == "__main__":
    main()
