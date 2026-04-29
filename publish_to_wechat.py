#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import requests
from datetime import datetime

APP_ID = os.environ.get("WECHAT_APP_ID", "")
APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")

def get_access_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}"
    print(f"正在获取 access_token...")
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if "access_token" in data:
            print(f"✅ 获取成功")
            return data["access_token"]
        else:
            print(f"❌ 失败: {data}")
            return None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return None

def add_draft(token, title, content):
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    # 简单转义
    content = content.replace('\\', '\\\\').replace('"', '\\"')
    html = f"<p>{content.replace(chr(10), '</p><p>')}</p>"
    data = {
        "articles": [{
            "title": title,
            "author": "股市晴雨表",
            "content": html,
            "digest": content[:100].replace(chr(10), ' '),
            "content_source_url": "",
            "need_open_comment": 0,
            "only_fans_can_comment": 0
        }]
    }
    print(f"正在上传草稿...")
    try:
        resp = requests.post(url, json=data, timeout=30)
        result = resp.json()
        if "media_id" in result:
            print(f"✅ 草稿上传成功！media_id: {result['media_id']}")
            return True
        else:
            print(f"❌ 上传失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False

def main():
    print("="*40)
    print("微信公众号发布工具")
    print("="*40)
    if not APP_ID or not APP_SECRET:
        print("❌ 错误：未设置 WECHAT_APP_ID 和 WECHAT_APP_SECRET")
        return 1
    if not os.path.exists("output.md"):
        print("❌ 错误：找不到 output.md 文件")
        return 1
    with open("output.md", "r", encoding="utf-8") as f:
        content = f.read()
    title = f"📊 股市晴雨表 {datetime.now().strftime('%Y-%m-%d')}"
    print(f"标题: {title}")
    print(f"内容长度: {len(content)} 字符")
    token = get_access_token()
    if not token:
        return 1
    if add_draft(token, title, content):
        print("✅ 发布成功！请去公众号后台草稿箱查看")
        return 0
    else:
        print("❌ 发布失败")
        return 1

if __name__ == "__main__":
    exit(main())
