#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号发布脚本 - 直接上传草稿箱
"""

import os
import json
import requests
from datetime import datetime

APP_ID = os.environ.get("WECHAT_APP_ID", "")
APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")

def get_access_token():
    """获取 access_token"""
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}"
    
    print(f"正在获取 access_token...")
    print(f"AppID: {APP_ID[:5]}...{APP_ID[-5:] if len(APP_ID) > 10 else ''}")
    
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if "access_token" in data:
            token = data["access_token"]
            print(f"✅ access_token 获取成功: {token[:20]}...")
            return token
        else:
            print(f"❌ 获取失败: {json.dumps(data, ensure_ascii=False)}")
            return None
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None

def add_draft(access_token, title, content):
    """添加草稿"""
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={access_token}"
    
    # 简单转换 Markdown 到 HTML
    html = content.replace('\n', '<br/>')
    html = html.replace('# ', '<h1>').replace(' #', '</h1>')
    html = html.replace('## ', '<h2>').replace(' ##', '</h2>')
    
    data = {
        "articles": [{
            "title": title,
            "author": "股市晴雨表",
            "content": html,
            "digest": content[:200].replace('\n', ' '),
            "content_source_url": "",
            "need_open_comment": 0,
            "only_fans_can_comment": 0
        }]
    }
    
    print(f"正在上传草稿...")
    print(f"标题: {title}")
    print(f"内容长度: {len(content)} 字符")
    
    try:
        resp = requests.post(url, json=data, timeout=30)
        result = resp.json()
        
        if "media_id" in result:
            print(f"✅ 草稿上传成功！media_id: {result['media_id']}")
            return True
        else:
            print(f"❌ 上传失败: {json.dumps(result, ensure_ascii=False)}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def main():
    print("=" * 50)
    print("微信公众号发布工具")
    print("=" * 50)
    
    # 检查配置
    if not APP_ID or not APP_SECRET:
        print("❌ 错误：未设置环境变量")
        print("请确保 WECHAT_APP_ID 和 WECHAT_APP_SECRET 已配置")
        return 1
    
    # 读取报告文件
    if not os.path.exists("output.md"):
        print("❌ 错误：找不到 output.md 文件")
        return 1
    
    with open("output.md", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 生成标题
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"📊 股市估值晴雨表 {today}"
    
    print(f"📄 文件名: output.md")
    print(f"📝 标题: {title}")
    
    # 获取 token
    token = get_access_token()
    if not token:
        return 1
    
    # 上传草稿
    if add_draft(token, title, content):
        print("\n✅ 发布成功！请登录公众号后台查看草稿箱")
        return 0
    else:
        print("\n❌ 发布失败")
        return 1

if __name__ == "__main__":
    exit(main())
