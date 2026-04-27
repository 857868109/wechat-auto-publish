#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号发布脚本
将 Markdown 文件发布到公众号草稿箱
"""

import os
import json
import requests
from datetime import datetime

# 从环境变量读取配置
APP_ID = os.environ.get("WECHAT_APP_ID", "")
APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")

def get_access_token():
    """获取微信 access_token"""
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}"
    
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if "access_token" in data:
            print(f"✅ 获取 access_token 成功")
            return data["access_token"]
        else:
            print(f"❌ 获取 access_token 失败: {data}")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def markdown_to_wechat_html(content):
    """将 Markdown 简单转换为微信 HTML"""
    html = content
    
    # 标题
    import re
    html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    
    # 粗体
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    
    # 斜体
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    
    # 表格简单处理
    html = re.sub(r'\|(.+)\|', r'<table><tr>\1</tr></table>', html)
    html = re.sub(r'\|:--+\|', r'', html)  # 去掉表格分隔行
    
    # 换行
    html = html.replace('\n\n', '</p><p>')
    html = '<p>' + html + '</p>'
    html = html.replace('<p><h1>', '<h1>').replace('</h1></p>', '</h1>')
    html = html.replace('<p><h2>', '<h2>').replace('</h2></p>', '</h2>')
    html = html.replace('<p><h3>', '<h3>').replace('</h3></p>', '</h3>')
    html = html.replace('<p><table>', '<table>').replace('</table></p>', '</table>')
    
    return html

def upload_news_draft(access_token, title, content, thumb_media_id=None):
    """上传图文草稿"""
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={access_token}"
    
    # 转换内容为 HTML
    html_content = markdown_to_wechat_html(content)
    
    # 构建文章数据
    articles = {
        "articles": [
            {
                "title": title,
                "author": "股市晴雨表",
                "content": html_content,
                "digest": content[:100].replace('\n', ' ') + "...",
                "content_source_url": "",
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0
            }
        ]
    }
    
    try:
        resp = requests.post(url, json=articles, timeout=30)
        data = resp.json()
        
        if "media_id" in data:
            print(f"✅ 草稿上传成功！media_id: {data['media_id']}")
            return data["media_id"]
        else:
            print(f"❌ 上传失败: {data}")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def main():
    """主函数"""
    print("=" * 50)
    print("开始发布到微信公众号...")
    print("=" * 50)
    
    # 检查环境变量
    if not APP_ID or not APP_SECRET:
        print("❌ 错误: 未设置 WECHAT_APP_ID 或 WECHAT_APP_SECRET")
        print("请在 GitHub Secrets 中配置这两个变量")
        return 1
    
    # 读取生成的 Markdown 文件
    markdown_file = "output.md"
    if not os.path.exists(markdown_file):
        print(f"❌ 错误: 找不到文件 {markdown_file}")
        print("请先运行 valuation_wechat.py 生成报告")
        return 1
    
    with open(markdown_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 生成标题（日期 + 报告）
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"📊 股市估值晴雨表 - {today}"
    
    print(f"📄 文章标题: {title}")
    print(f"📝 文章长度: {len(content)} 字符")
    
    # 获取 access_token
    access_token = get_access_token()
    if not access_token:
        return 1
    
    # 上传草稿（暂时没有封面图）
    media_id = upload_news_draft(access_token, title, content)
    
    if media_id:
        print("\n" + "=" * 50)
        print("✅ 发布成功！")
        print("📱 请登录微信公众号后台 -> 草稿箱 查看")
        print("=" * 50)
        return 0
    else:
        print("\n❌ 发布失败")
        return 1

if __name__ == "__main__":
    exit(main())
