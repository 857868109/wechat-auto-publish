#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票基金估值管理系统 - 微信公众号云函数版
适用于微信公众号云函数/云托管部署

移除了 tkinter GUI 依赖,改为输出 Markdown/HTML 格式
"""

import json
import os
import re
import statistics
import time as time_module
from datetime import datetime, timedelta, time

import requests
import baostock as bs
import pandas as pd


# ============================================================================
# 配置常量模块
# ============================================================================

# 配置文件路径
CONFIG_FILE = "my_portfolio.json"

# 用户投资组合存储目录 (云函数持久化存储)
USER_DATA_DIR = "/tmp/user_portfolios"  # 云函数临时目录,或使用云数据库

# 微信消息指令前缀
CMD_PREFIX = "/"

# 恐贪指数颜色配置
FEAR_GREED_COLORS = {
    "extreme_fear": "#006400",
    "fear": "#228B22",
    "neutral": "#B8860B",
    "greed": "#D2691E",
    "extreme_greed": "#8B0000",
}

# 恐贪指数分值区间
FEAR_GREED_INTERVALS = [
    ("0～20", "极度恐惧", "#006400"),
    ("21～40", "恐惧", "#228B22"),
    ("41～60", "中性", "#B8860B"),
    ("61～80", "贪婪", "#D2691E"),
    ("81～100", "极度贪婪", "#8B0000")
]

# 估值颜色配置
VALUATION_COLORS = {
    "extreme_low": "#006400",
    "low": "#32CD32",
    "fair": "#FFD700",
    "high": "#FF8C00",
    "extreme_high": "#8B0000",
}

# 估值标记符号
VALUATION_MARKERS = {
    "#006400": "[--]",
    "#32CD32": "[-]",
    "#FFD700": "[=]",
    "#FF8C00": "[+]",
    "#8B0000": "[++]",
}

# 默认投资组合
DEFAULT_PORTFOLIO_FUNDS = ["512170", "001594"]
DEFAULT_PORTFOLIO_STOCKS = ["601727", "000001"]

# HTTP请求头
HEADERS_EASTMONEY = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'http://quote.eastmoney.com/'
}

HEADERS_FUND = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/'
}

HEADERS_SIMPLE = {'User-Agent': 'Mozilla/5.0'}

# 网络请求重试配置
REQUEST_RETRY_COUNT = 3
REQUEST_RETRY_DELAY = 1.0


# ============================================================================
# 工具函数模块
# ============================================================================

def safe_request(url, method='GET', **kwargs):
    """带重试机制的安全网络请求"""
    for attempt in range(REQUEST_RETRY_COUNT):
        try:
            if method.upper() == 'GET':
                response = requests.get(url, **kwargs)
            else:
                response = requests.post(url, **kwargs)
            return response
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as e:
            if attempt < REQUEST_RETRY_COUNT - 1:
                time_module.sleep(REQUEST_RETRY_DELAY * (attempt + 1))
            else:
                raise e
    return None


# ============================================================================
# 投资组合数据管理模块
# ============================================================================

class PortfolioManager:
    """投资组合管理器"""

    def __init__(self):
        self.data = self.load()

    def load(self):
        """加载投资组合配置"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        default = {
            "funds": list(DEFAULT_PORTFOLIO_FUNDS),
            "stocks": list(DEFAULT_PORTFOLIO_STOCKS),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save(default)
        return default

    def save(self, portfolio=None):
        """保存投资组合配置"""
        if portfolio is None:
            portfolio = self.data
        portfolio["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(portfolio, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    @property
    def funds(self):
        return self.data.get("funds", [])

    @property
    def stocks(self):
        return self.data.get("stocks", [])

    def add_fund(self, code):
        """添加基金代码"""
        if "funds" not in self.data:
            self.data["funds"] = []
        if code not in self.data["funds"]:
            self.data["funds"].append(code)
            self.save()
            return True
        return False

    def add_stock(self, code):
        """添加股票代码"""
        if "stocks" not in self.data:
            self.data["stocks"] = []
        if code not in self.data["stocks"]:
            self.data["stocks"].append(code)
            self.save()
            return True
        return False

    def remove_fund(self, code):
        """删除基金代码"""
        if code in self.data.get("funds", []):
            self.data["funds"].remove(code)
            self.save()
            return True
        return False

    def remove_stock(self, code):
        """删除股票代码"""
        if code in self.data.get("stocks", []):
            self.data["stocks"].remove(code)
            self.save()
            return True
        return False

    def has_code(self, code):
        """检查代码是否已存在"""
        return code in self.funds or code in self.stocks


# ============================================================================
# 用户投资组合管理 (支持多用户隔离)
# ============================================================================

class UserPortfolioManager:
    """用户投资组合管理器 - 支持多用户隔离存储"""

    def __init__(self, user_id):
        """
        Args:
            user_id: 微信用户 OpenID
        """
        self.user_id = user_id
        self.config_file = self._get_user_config_path()
        self.data = self.load()

    def _get_user_config_path(self):
        """获取用户配置文件路径"""
        # 确保用户数据目录存在
        if not os.path.exists(USER_DATA_DIR):
            try:
                os.makedirs(USER_DATA_DIR, exist_ok=True)
            except:
                pass
        return os.path.join(USER_DATA_DIR, f"{self.user_id}.json")

    def load(self):
        """加载用户投资组合"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        # 新用户返回空组合
        return {
            "user_id": self.user_id,
            "funds": [],
            "stocks": [],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def save(self):
        """保存用户投资组合"""
        self.data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    @property
    def funds(self):
        return self.data.get("funds", [])

    @property
    def stocks(self):
        return self.data.get("stocks", [])

    def add_fund(self, code):
        """添加基金"""
        if "funds" not in self.data:
            self.data["funds"] = []
        if code not in self.data["funds"]:
            self.data["funds"].append(code)
            self.save()
            return True
        return False

    def add_stock(self, code):
        """添加股票"""
        if "stocks" not in self.data:
            self.data["stocks"] = []
        if code not in self.data["stocks"]:
            self.data["stocks"].append(code)
            self.save()
            return True
        return False

    def remove_fund(self, code):
        """删除基金"""
        if code in self.data.get("funds", []):
            self.data["funds"].remove(code)
            self.save()
            return True
        return False

    def remove_stock(self, code):
        """删除股票"""
        if code in self.data.get("stocks", []):
            self.data["stocks"].remove(code)
            self.save()
            return True
        return False

    def has_code(self, code):
        """检查代码是否存在"""
        return code in self.funds or code in self.stocks

    def clear_all(self):
        """清空所有标的"""
        self.data["funds"] = []
        self.data["stocks"] = []
        self.save()


# ============================================================================
# 微信消息指令解析器
# ============================================================================

def parse_command(message):
    """
    解析微信消息指令
    支持的指令格式:
        /add 512170        - 添加标的(自动识别基金/股票)
        /add 基金 512170   - 添加基金
        /add 股票 601727   - 添加股票
        /del 512170        - 删除标的
        /del 基金 512170   - 删除基金
        /del 股票 601727   - 删除股票
        /list              - 查看我的关注列表
        /clear             - 清空所有关注
        /help              - 查看帮助
        其他消息            - 查看估值报告

    Returns:
        (command, args) 或 (None, None)
    """
    message = message.strip()

    # 非指令消息
    if not message.startswith(CMD_PREFIX):
        return None, None

    # 移除前缀
    cmd_text = message[len(CMD_PREFIX):].strip()

    # 空指令
    if not cmd_text:
        return None, None

    # 解析指令和参数
    parts = cmd_text.split()
    command = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []

    return command, args


def handle_add_command(user_portfolio, args):
    """
    处理添加指令
    Args:
        user_portfolio: UserPortfolioManager 实例
        args: 指令参数
    Returns:
        回复消息
    """
    if not args:
        return "❌ 请指定要添加的代码\n\n用法: /add 代码\n      /add 基金 代码\n      /add 股票 代码"

    # 判断是否指定了类型
    if args[0] in ["基金", "fund", "f"]:
        if len(args) < 2:
            return "❌ 请指定基金代码"
        code = args[1].strip()
        code_type = "fund"
    elif args[0] in ["股票", "stock", "s"]:
        if len(args) < 2:
            return "❌ 请指定股票代码"
        code = args[1].strip()
        code_type = "stock"
    else:
        # 自动识别
        code = args[0].strip()
        code_type = None

    # 验证代码格式
    if not code.isdigit():
        return f"❌ 代码格式错误: {code}\n代码应为纯数字"

    # 补零到6位
    code = code.zfill(6)

    # 检查是否已存在
    if user_portfolio.has_code(code):
        return f"⚠️ 代码 {code} 已在关注列表中"

    # 自动识别类型
    if code_type is None:
        # 先尝试基金
        fund_info = get_fund_info(code)
        if fund_info:
            user_portfolio.add_fund(code)
            return f"✅ 添加基金成功\n\n{fund_info['name']} ({code})\n当前净值: {fund_info.get('nav', 'N/A')}\n今日涨跌: {fund_info.get('change', 'N/A')}%"

        # 再尝试股票
        stock_info = get_stock_info(code)
        if stock_info:
            user_portfolio.add_stock(code)
            return f"✅ 添加股票成功\n\n{stock_info['name']} ({code})\n当前价格: {stock_info.get('price', 'N/A')}\n今日涨跌: {stock_info.get('change', 'N/A')}%"

        return f"❌ 代码 {code} 无效或获取失败"

    # 指定类型添加
    if code_type == "fund":
        fund_info = get_fund_info(code)
        if fund_info:
            user_portfolio.add_fund(code)
            return f"✅ 添加基金成功\n\n{fund_info['name']} ({code})\n当前净值: {fund_info.get('nav', 'N/A')}\n今日涨跌: {fund_info.get('change', 'N/A')}%"
        return f"❌ 基金代码 {code} 无效或获取失败"

    else:  # stock
        stock_info = get_stock_info(code)
        if stock_info:
            user_portfolio.add_stock(code)
            return f"✅ 添加股票成功\n\n{stock_info['name']} ({code})\n当前价格: {stock_info.get('price', 'N/A')}\n今日涨跌: {stock_info.get('change', 'N/A')}%"
        return f"❌ 股票代码 {code} 无效或获取失败"


def handle_del_command(user_portfolio, args):
    """
    处理删除指令
    Args:
        user_portfolio: UserPortfolioManager 实例
        args: 指令参数
    Returns:
        回复消息
    """
    if not args:
        return "❌ 请指定要删除的代码\n\n用法: /del 代码\n      /del 基金 代码\n      /del 股票 代码"

    # 判断是否指定了类型
    if args[0] in ["基金", "fund", "f"]:
        if len(args) < 2:
            return "❌ 请指定基金代码"
        code = args[1].strip().zfill(6)
        if user_portfolio.remove_fund(code):
            return f"✅ 已删除基金 {code}"
        return f"⚠️ 基金 {code} 不在关注列表中"

    elif args[0] in ["股票", "stock", "s"]:
        if len(args) < 2:
            return "❌ 请指定股票代码"
        code = args[1].strip().zfill(6)
        if user_portfolio.remove_stock(code):
            return f"✅ 已删除股票 {code}"
        return f"⚠️ 股票 {code} 不在关注列表中"

    else:
        # 自动匹配
        code = args[0].strip().zfill(6)

        # 尝试删除基金
        if user_portfolio.remove_fund(code):
            return f"✅ 已删除基金 {code}"

        # 尝试删除股票
        if user_portfolio.remove_stock(code):
            return f"✅ 已删除股票 {code}"

        return f"⚠️ 代码 {code} 不在关注列表中"


def handle_list_command(user_portfolio):
    """处理查看列表指令"""
    funds = user_portfolio.funds
    stocks = user_portfolio.stocks

    if not funds and not stocks:
        return "📭 你的关注列表为空\n\n使用 /add 代码 添加关注标的"

    lines = ["📋 我的关注列表", ""]

    if funds:
        lines.append("【基金】")
        for code in funds:
            info = get_fund_info(code)
            if info:
                lines.append(f"  • {code} {info.get('name', '未知')}")
            else:
                lines.append(f"  • {code} (获取失败)")
        lines.append("")

    if stocks:
        lines.append("【股票】")
        for code in stocks:
            info = get_stock_info(code)
            if info:
                lines.append(f"  • {code} {info.get('name', '未知')}")
            else:
                lines.append(f"  • {code} (获取失败)")
        lines.append("")

    lines.append(f"共 {len(funds)} 只基金, {len(stocks)} 只股票")

    return "\n".join(lines)


def handle_help_command():
    """处理帮助指令"""
    return """📖 使用帮助

【指令列表】
/add 代码        添加标的(自动识别)
/add 基金 代码   添加基金
/add 股票 代码   添加股票
/del 代码        删除标的
/del 基金 代码   删除基金
/del 股票 代码   删除股票
/list            查看关注列表
/clear           清空所有关注
/help            查看帮助

【示例】
/add 512170      添加医疗ETF
/add 股票 601727 添加上汽集团
/del 512170      删除医疗ETF

【其他】
发送任意非指令消息,将返回估值报告"""


# ============================================================================
# 估值计算模块
# ============================================================================

def get_fear_greed_status(value):
    """根据恐贪指数值返回状态和颜色"""
    if value < 25:
        return "极度恐惧", FEAR_GREED_COLORS["extreme_fear"]
    elif value < 45:
        return "恐惧", FEAR_GREED_COLORS["fear"]
    elif value < 55:
        return "中性", FEAR_GREED_COLORS["neutral"]
    elif value < 75:
        return "贪婪", FEAR_GREED_COLORS["greed"]
    else:
        return "极度贪婪", FEAR_GREED_COLORS["extreme_greed"]


def get_valuation_color_and_advice(percentile):
    """根据估值百分位返回颜色和操作建议"""
    if percentile < 10:
        return VALUATION_COLORS["extreme_low"], "极度低估", "强烈建议买入"
    elif percentile < 30:
        return VALUATION_COLORS["low"], "低估", "建议买入"
    elif percentile < 70:
        return VALUATION_COLORS["fair"], "合理估值", "持有观望"
    elif percentile < 90:
        return VALUATION_COLORS["high"], "高估", "建议减仓"
    else:
        return VALUATION_COLORS["extreme_high"], "极度高估", "强烈建议卖出"


def format_number(value, max_decimals=3):
    """格式化数值"""
    if value == "N/A" or value is None:
        return "N/A"
    try:
        num = float(value)
        if num == int(num):
            return str(int(num))
        formatted = f"{num:.{max_decimals}f}".rstrip('0').rstrip('.')
        return formatted
    except:
        return str(value)


def get_stock_sector(code):
    """获取股票所属板块"""
    if code.startswith('688'):
        return "科创板"
    elif code.startswith('300'):
        return "创业板"
    elif code.startswith('00'):
        return "主板"
    elif code.startswith('60'):
        return "主板"
    else:
        return "其他"


# ============================================================================
# 数据获取模块
# ============================================================================

def get_fear_greed_index():
    """获取恐贪指数"""
    try:
        return calculate_fear_greed_from_market()
    except Exception as e:
        raise Exception(f"无法获取恐贪指数数据: {str(e)}")


def calculate_fear_greed_from_market():
    """基于市场数据计算恐贪指数"""
    # 因子1: 涨跌比
    up_down_score = 50
    up_count = 0
    down_count = 0
    limit_up = 0
    limit_down = 0
    try:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'pn': 1, 'pz': 5000, 'po': 1, 'np': 1,
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'm:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23',
            'fields': 'f3,f2'
        }
        res = safe_request(url, params=params, headers=HEADERS_EASTMONEY, timeout=10)
        if res and res.status_code == 200:
            data = res.json()
            if data and 'data' in data and data['data'] and 'diff' in data['data']:
                stocks = data['data']['diff']
                up_count = sum(1 for s in stocks if s.get('f3', 0) > 0)
                down_count = sum(1 for s in stocks if s.get('f3', 0) < 0)
                limit_up = sum(1 for s in stocks if s.get('f3', 0) >= 9.9)
                limit_down = sum(1 for s in stocks if s.get('f3', 0) <= -9.9)
                if down_count > 0:
                    up_down_score = _calc_up_down_score(up_count / down_count)
    except:
        pass

    # 因子2: 涨跌幅 + 因子3: 成交额
    price_score = 50
    activity_score = 50
    change_pct = 0
    try:
        url = "http://push2.eastmoney.com/api/qt/stock/get?secid=1.000001&fields=f43,f48,f170"
        res = safe_request(url, headers=HEADERS_EASTMONEY, timeout=5)
        if res and res.status_code == 200:
            data = res.json()
            if data and 'data' in data and data['data']:
                d = data['data']
                change_pct = d.get('f170', 0) / 100
                amount = d.get('f48', 0)
                price_score = _calc_price_score(change_pct)
                activity_score = _calc_activity_score(amount / 100000000)
    except:
        pass

    # 因子4: 涨停跌停比
    limit_score = 50
    if limit_down > 0:
        limit_score = _calc_limit_score(limit_up / limit_down)
    elif limit_up > 0:
        limit_score = 90

    # 因子5: 市场波动
    volatility_score = 50
    try:
        volatility_score = _calc_volatility_score()
    except:
        pass

    # 综合得分
    score = int(
        up_down_score * 0.40 +
        price_score * 0.25 +
        activity_score * 0.15 +
        limit_score * 0.10 +
        volatility_score * 0.10
    )
    score = max(0, min(100, score))

    history = _get_fear_greed_history(score)

    return {
        'current': score,
        'yesterday': history.get('yesterday', score),
        'week_ago': history.get('week_ago', score),
        'month_ago': history.get('month_ago', score),
        'year_ago': history.get('year_ago', 50),
        'status': get_fear_greed_status(score)[0],
        'color': get_fear_greed_status(score)[1],
        'source': '市场数据计算'
    }


def _calc_up_down_score(ratio):
    if ratio > 3:
        return 85 + min(15, (ratio - 3) * 3)
    elif ratio > 2:
        return 70 + (ratio - 2) * 15
    elif ratio > 1:
        return 55 + (ratio - 1) * 15
    elif ratio > 0.5:
        return 40 + (ratio - 0.5) * 30
    elif ratio > 0.33:
        return 25 + (ratio - 0.33) * 45
    else:
        return max(5, ratio * 75)


def _calc_price_score(change_pct):
    if change_pct > 5: return 95
    elif change_pct > 3: return 85
    elif change_pct > 1: return 70
    elif change_pct > 0: return 60
    elif change_pct > -1: return 50
    elif change_pct > -3: return 35
    elif change_pct > -5: return 20
    else: return 10


def _calc_activity_score(amount_yi):
    if amount_yi > 10000: return 90
    elif amount_yi > 8000: return 80
    elif amount_yi > 6000: return 70
    elif amount_yi > 4000: return 60
    elif amount_yi > 3000: return 50
    elif amount_yi > 2000: return 40
    else: return 30


def _calc_limit_score(ratio):
    if ratio > 5: return 90
    elif ratio > 3: return 80
    elif ratio > 2: return 70
    elif ratio > 1: return 60
    elif ratio > 0.5: return 40
    elif ratio > 0.2: return 25
    else: return 10


def _calc_volatility_score():
    try:
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            'secid': '1.000001',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',
            'fqt': '1',
            'beg': (datetime.now() - timedelta(days=40)).strftime('%Y%m%d'),
            'end': datetime.now().strftime('%Y%m%d'),
            'lmt': 20
        }
        res = safe_request(url, params=params, headers=HEADERS_EASTMONEY, timeout=5)
        if res and res.status_code == 200:
            data = res.json()
            if data and 'data' in data and data['data'] and 'klines' in data['data']:
                klines = data['data']['klines']
                if len(klines) >= 5:
                    changes = []
                    for kline in klines:
                        parts = kline.split(',')
                        if len(parts) >= 4:
                            close = float(parts[2])
                            pre_close = float(parts[3])
                            if pre_close > 0:
                                changes.append((close / pre_close - 1) * 100)
                    if len(changes) >= 5:
                        std = statistics.stdev(changes)
                        if std < 0.5: return 80
                        elif std < 1.0: return 60
                        elif std < 1.5: return 45
                        elif std < 2.0: return 35
                        else: return 20
    except:
        pass
    return 50


def _get_fear_greed_history(current_score):
    history = {}
    target_days = {
        'yesterday': 1,
        'week_ago': 7,
        'month_ago': 30,
        'year_ago': 365
    }
    try:
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            'secid': '1.000001',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',
            'fqt': '1',
            'beg': (datetime.now() - timedelta(days=400)).strftime('%Y%m%d'),
            'end': datetime.now().strftime('%Y%m%d'),
            'lmt': 250
        }
        res = safe_request(url, params=params, headers=HEADERS_EASTMONEY, timeout=5)
        if not res or res.status_code != 200:
            return history
        data = res.json()
        if not data or 'data' not in data or not data['data'] or 'klines' not in data['data']:
            return history

        klines = data['data']['klines']
        if len(klines) < 2:
            return history

        parsed = []
        for kline in klines:
            parts = kline.split(',')
            if len(parts) >= 7:
                parsed.append({
                    'date': parts[0],
                    'close': float(parts[2]),
                    'pre_close': float(parts[3]),
                    'amount': float(parts[6]) if parts[6] != '-' else 0
                })

        if len(parsed) < 2:
            return history

        today_str = datetime.now().strftime('%Y-%m-%d')

        for key, days in target_days.items():
            target_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            best_idx = -1
            min_diff = 999
            for i, p in enumerate(parsed):
                if p['date'] <= today_str:
                    diff = abs((datetime.strptime(p['date'], '%Y-%m-%d') -
                                datetime.strptime(target_date, '%Y-%m-%d')).days)
                    if diff < min_diff:
                        min_diff = diff
                        best_idx = i

            if best_idx < 0:
                continue

            p = parsed[best_idx]
            change_pct = (p['close'] / p['pre_close'] - 1) * 100 if p['pre_close'] > 0 else 0
            amount_yi = p['amount'] / 100000000

            ps = _calc_price_score(change_pct)
            as_ = _calc_activity_score(amount_yi)
            est_score = int(ps * 0.6 + as_ * 0.4)
            history[key] = max(0, min(100, est_score))

    except:
        pass
    return history


def get_fund_info(code):
    """获取基金信息"""
    try:
        url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        res = safe_request(url, timeout=5)
        if res:
            res_text = res.text
            if 'jsonpgz' in res_text:
                data_str = res_text.split('(')[1].split(')')[0]
                data = json.loads(data_str)
                fund_data = {
                    "code": code,
                    "name": data.get('name', '未知'),
                    "nav": data.get('gsz', '0'),
                    "change": data.get('gszzl', '0')
                }
                _fill_fund_history(code, fund_data)
                return fund_data
    except:
        pass
    return None


def _fill_fund_history(code, fund_data):
    """填充基金历史涨跌幅和估值位置"""
    na_fields = {"change_1w", "change_1m", "change_3m", "change_6m", "change_1y"}
    try:
        detail_url = f"http://fund.eastmoney.com/pingzhongdata/{code}.js"
        detail_res = safe_request(detail_url, headers=HEADERS_SIMPLE, timeout=5)
        if not detail_res or detail_res.status_code != 200:
            for f in na_fields: fund_data[f] = "N/A"
            return

        pattern = r'Data_netWorthTrend\s*=\s*(\[{.*?}\])'
        match = re.search(pattern, detail_res.text, re.DOTALL)
        if not match:
            for f in na_fields: fund_data[f] = "N/A"
            return

        nav_trend = json.loads(match.group(1))
        if not nav_trend:
            for f in na_fields: fund_data[f] = "N/A"
            return

        nav_values = [item['y'] for item in nav_trend]
        current_nav = nav_values[-1]

        periods = [(5, "change_1w"), (20, "change_1m"), (60, "change_3m"),
                    (120, "change_6m"), (240, "change_1y")]
        for days, key in periods:
            if len(nav_values) >= days:
                change = (current_nav / nav_values[-days] - 1) * 100
                fund_data[key] = f"{change:.2f}"
            else:
                fund_data[key] = "N/A"

        if len(nav_values) >= 2400:
            nav_10y = nav_values[-2400:]
            below = sum(1 for v in nav_10y if v < current_nav)
            fund_data["position_10y"] = f"{(below / (len(nav_10y) - 1)) * 100:.1f}"
        elif len(nav_values) >= 500:
            below = sum(1 for v in nav_values if v < current_nav)
            fund_data["position_10y"] = f"{(below / (len(nav_values) - 1)) * 100:.1f}"
        else:
            fund_data["position_10y"] = "N/A"
    except:
        for f in na_fields: fund_data[f] = "N/A"


def get_stock_info(code):
    """获取股票信息"""
    bs_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
    lg = None
    try:
        lg = bs.login()
        if lg.error_code != '0':
            return None

        today = datetime.now().strftime("%Y-%m-%d")
        name = _get_stock_name(code)

        rs = bs.query_history_k_data_plus(
            bs_code, "date,code,open,high,low,close,preclose,pctChg",
            start_date=(datetime.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
            end_date=today, frequency="d", adjustflag="3"
        )
        price_data = []
        while (rs.error_code == '0') & rs.next():
            price_data.append(rs.get_row_data())

        if not price_data:
            return None

        latest = price_data[-1]
        stock_data = {
            "code": code, "name": name,
            "date": latest[0], "price": latest[5],
            "change": latest[7]
        }

        _fill_stock_history(bs_code, today, stock_data)
        return stock_data
    except:
        pass
    finally:
        if lg is not None:
            try:
                bs.logout()
            except:
                pass
    return None


def _get_stock_name(code):
    """获取股票名称"""
    try:
        secid = f"1.{code}" if code.startswith('6') else f"0.{code}"
        url = f"http://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f58"
        res = safe_request(url, headers=HEADERS_EASTMONEY, timeout=3)
        if res and res.status_code == 200:
            data = res.json()
            if data and 'data' in data and data['data']:
                return data['data'].get('f58', code)
    except:
        pass
    return code


def _fill_stock_history(bs_code, today, stock_data):
    """填充股票历史涨跌幅和估值位置"""
    na_fields = {"change_1w", "change_1m", "change_3m", "change_6m", "change_1y", "position_10y"}
    try:
        rs_all = bs.query_history_k_data_plus(
            bs_code, "date,close",
            start_date=(datetime.now() - pd.Timedelta(days=3650)).strftime("%Y-%m-%d"),
            end_date=today, frequency="d", adjustflag="3"
        )
        all_data = []
        while (rs_all.error_code == '0') & rs_all.next():
            all_data.append(rs_all.get_row_data())

        total_days = len(all_data)
        periods = [(5, "change_1w"), (20, "change_1m"), (60, "change_3m"),
                    (120, "change_6m"), (240, "change_1y")]
        for days, key in periods:
            if total_days >= days:
                change = (float(all_data[-1][1]) / float(all_data[-days][1]) - 1) * 100
                stock_data[key] = f"{change:.2f}"
            else:
                stock_data[key] = "N/A"

        if total_days >= 2400:
            prices_10y = [float(item[1]) for item in all_data[-2400:]]
            current_price = float(all_data[-1][1])
            below = sum(1 for p in prices_10y if p < current_price)
            stock_data["position_10y"] = f"{(below / (len(prices_10y) - 1)) * 100:.1f}"
        elif total_days >= 500:
            prices_all = [float(item[1]) for item in all_data]
            current_price = float(all_data[-1][1])
            below = sum(1 for p in prices_all if p < current_price)
            stock_data["position_10y"] = f"{(below / (len(prices_all) - 1)) * 100:.1f}"
        else:
            stock_data["position_10y"] = "N/A"
    except:
        for f in na_fields: stock_data[f] = "N/A"


# ============================================================================
# 格式化输出模块 (替代 tkinter UI)
# ============================================================================

def format_fear_greed_markdown(data):
    """将恐贪指数格式化为 Markdown"""
    if not data:
        return "⚠️ 恐贪指数获取失败"

    current = data.get('current', 50)
    status = data.get('status', '中性')
    color = data.get('color', '#B8860B')

    # 状态表情映射
    status_emoji = {
        "极度恐惧": "😱",
        "恐惧": "😨",
        "中性": "😐",
        "贪婪": "😏",
        "极度贪婪": "🤑"
    }
    emoji = status_emoji.get(status, "📊")

    lines = [
        f"## {emoji} A股恐贪指数",
        "",
        f"**当前值**: {current} ({status})",
        "",
        "| 时段 | 数值 | 状态 |",
        "|:----:|:----:|:----:|",
    ]

    time_data = [
        ("当前", data.get('current')),
        ("1日前", data.get('yesterday')),
        ("1周前", data.get('week_ago')),
        ("1月前", data.get('month_ago')),
        ("1年前", data.get('year_ago'))
    ]

    for label, val in time_data:
        if val is not None:
            s, _ = get_fear_greed_status(val)
            lines.append(f"| {label} | {val} | {s} |")
        else:
            lines.append(f"| {label} | N/A | - |")

    # 操作建议
    if current < 20:
        advice = "💡 极度恐惧,逢低布局"
    elif current < 40:
        advice = "💡 恐惧偏多,可逐步建仓"
    elif current < 60:
        advice = "💡 情绪中性,持有观望"
    elif current < 80:
        advice = "💡 贪婪偏多,注意减仓"
    else:
        advice = "💡 极度贪婪,考虑离场"

    lines.extend(["", advice])

    return "\n".join(lines)


def format_valuation_markdown(portfolio):
    """将估值表格格式化为 Markdown"""
    lines = [
        "## 📊 实时估值表",
        "",
        "| 代码 | 名称 | 当前价 | 今日涨跌 | 近1周 | 近1月 | 近3月 | 估值位置 | 估值状态 | 操作建议 |",
        "|:----:|:----:|:------:|:--------:|:-----:|:-----:|:-----:|:--------:|:--------:|:--------:|"
    ]

    errors = []

    # 获取基金数据
    for code in portfolio.funds:
        try:
            info = get_fund_info(code)
            if info:
                row = _build_markdown_row(code, info, 'nav')
                lines.append(row)
            else:
                lines.append(f"| {code} | 获取失败 | - | - | - | - | - | - | - | - |")
                errors.append(f"基金 {code}")
        except Exception as e:
            lines.append(f"| {code} | 获取失败 | - | - | - | - | - | - | - | - |")
            errors.append(f"基金 {code}: {str(e)}")

    # 获取股票数据
    for code in portfolio.stocks:
        try:
            info = get_stock_info(code)
            if info:
                row = _build_markdown_row(code, info, 'price')
                lines.append(row)
            else:
                lines.append(f"| {code} | 获取失败 | - | - | - | - | - | - | - | - |")
                errors.append(f"股票 {code}")
        except Exception as e:
            lines.append(f"| {code} | 获取失败 | - | - | - | - | - | - | - | - |")
            errors.append(f"股票 {code}: {str(e)}")

    # 添加更新时间和错误提示
    lines.extend([
        "",
        f"📅 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ])

    if errors:
        lines.extend([
            "",
            f"⚠️ 部分数据获取失败: {', '.join(errors)}"
        ])

    return "\n".join(lines)


def _build_markdown_row(code, info, price_key):
    """构建 Markdown 表格行"""
    position = info.get('position_10y', 'N/A')
    if position != "N/A":
        position_val = float(position)
        color, position_desc, advice = get_valuation_color_and_advice(position_val)
        marker = VALUATION_MARKERS.get(color, "")
    else:
        position_desc = "N/A"
        advice = "N/A"
        marker = ""

    name = info.get('name', '未知')[:6]  # 截断名称
    price = format_number(info.get(price_key, 'N/A'))
    change = f"{format_number(info.get('change', 'N/A'), 2)}%"
    change_1w = f"{format_number(info.get('change_1w', 'N/A'), 2)}%"
    change_1m = f"{format_number(info.get('change_1m', 'N/A'), 2)}%"
    change_3m = f"{format_number(info.get('change_3m', 'N/A'), 2)}%"
    pos_str = f"{marker}{format_number(position)}%" if position != "N/A" else "N/A"

    return f"| {code} | {name} | {price} | {change} | {change_1w} | {change_1m} | {change_3m} | {pos_str} | {position_desc} | {advice} |"


def format_full_report():
    """生成完整报告 (Markdown 格式)"""
    lines = [
        "# 📈 你的股市晴雨表",
        "",
        "---",
        ""
    ]

    # 恐贪指数
    try:
        fg_data = get_fear_greed_index()
        lines.append(format_fear_greed_markdown(fg_data))
    except Exception as e:
        lines.append(f"⚠️ 恐贪指数获取失败: {str(e)}")

    lines.extend(["", "---", ""])

    # 估值表格
    portfolio = PortfolioManager()
    lines.append(format_valuation_markdown(portfolio))

    lines.extend([
        "",
        "---",
        "",
        "### 📌 符号说明",
        "- `[--]` 极度低估,强烈买入信号",
        "- `[-]` 低估,买入信号",
        "- `[=]` 合理估值,持有观望",
        "- `[+]` 高估,减仓信号",
        "- `[++]` 极度高估,强烈卖出信号",
        "",
        "### ⚠️ 重要提醒",
        "1. 估值≠股价: 估值低不代表马上涨,估值高不代表马上跌",
        "2. 周期看位置,成长看增速",
        "3. 数据仅作为参考,不作为投资依据",
        "",
        f"🤖 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ])

    return "\n".join(lines)


# ============================================================================
# 微信公众号云函数入口
# ============================================================================

def main_handler(event, context):
    """
    微信公众号云函数入口
    Args:
        event: 云函数事件参数,包含:
            - FromUserName: 用户 OpenID
            - Content: 消息内容
        context: 云函数上下文
    Returns:
        微信消息响应
    """
    try:
        # 获取用户ID和消息内容
        user_id = event.get("FromUserName", "default")
        message = event.get("Content", "").strip()

        # 获取用户投资组合
        user_portfolio = UserPortfolioManager(user_id)

        # 解析指令
        command, args = parse_command(message)

        # 处理指令
        if command is not None:
            reply = handle_command(user_portfolio, command, args)
        else:
            # 非指令消息,返回估值报告
            reply = format_user_report(user_portfolio)

        # 返回微信消息格式
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "touser": user_id,
                "msgtype": "text",
                "text": {
                    "content": reply
                }
            }, ensure_ascii=False)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            }, ensure_ascii=False)
        }


def handle_command(user_portfolio, command, args):
    """
    处理用户指令
    Args:
        user_portfolio: UserPortfolioManager 实例
        command: 指令名称
        args: 指令参数
    Returns:
        回复消息
    """
    # 添加标的
    if command in ["add", "a", "添加", "加入"]:
        return handle_add_command(user_portfolio, args)

    # 删除标的
    elif command in ["del", "delete", "d", "删除", "移除"]:
        return handle_del_command(user_portfolio, args)

    # 查看列表
    elif command in ["list", "ls", "l", "列表", "查看"]:
        return handle_list_command(user_portfolio)

    # 清空所有
    elif command in ["clear", "清空", "重置"]:
        user_portfolio.clear_all()
        return "✅ 已清空所有关注标的"

    # 帮助
    elif command in ["help", "h", "帮助", "?"]:
        return handle_help_command()

    # 未知指令
    else:
        return f"❌ 未知指令: /{command}\n\n发送 /help 查看帮助"


def format_user_report(user_portfolio):
    """
    生成用户专属估值报告
    Args:
        user_portfolio: UserPortfolioManager 实例
    Returns:
        Markdown 格式报告
    """
    lines = [
        "# 📈 你的股市晴雨表",
        "",
        "---",
        ""
    ]

    # 恐贪指数
    try:
        fg_data = get_fear_greed_index()
        lines.append(format_fear_greed_markdown(fg_data))
    except Exception as e:
        lines.append(f"⚠️ 恐贪指数获取失败: {str(e)}")

    lines.extend(["", "---", ""])

    # 估值表格
    if user_portfolio.funds or user_portfolio.stocks:
        lines.append(format_valuation_markdown(user_portfolio))
    else:
        lines.extend([
            "## 📊 实时估值表",
            "",
            "📭 你的关注列表为空",
            "",
            "使用以下指令添加关注标的:",
            "- `/add 代码` 自动识别添加",
            "- `/add 基金 代码` 添加基金",
            "- `/add 股票 代码` 添加股票",
            "",
            "示例:",
            "- `/add 512170` 添加医疗ETF",
            "- `/add 股票 601727` 添加上汽集团"
        ])

    lines.extend([
        "",
        "---",
        "",
        "💡 发送 /help 查看更多指令",
        "",
        f"🤖 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ])

    return "\n".join(lines)


# ============================================================================
# 本地测试入口
# ============================================================================



if __name__ == "__main__":
    # 生成报告内容
    report = format_full_report()
    
    # 输出到控制台（方便查看日志）
    print(report)
    
    # 保存到文件（供 wenyan 发布工具使用）
    with open("output.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    print("\n✅ 报告已保存到 output.md")