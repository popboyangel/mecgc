# -*- coding: utf-8 -*-
"""
monitor_core.py
共享核心逻辑（被 main.py 界面进程 和 service.py 后台服务进程 共同引用）：
- 读写配置文件 / 状态文件（用文件而不是内存，是因为 UI 和后台服务是两个独立进程）
- 直接对 GoodChain 链的 RPC 节点发 JSON-RPC 请求，读取 DEX 交易对合约（LP Pair）
  的 getReserves()，取得 CGC / WGDC 储备数量（这就是浏览器 tokens 页面 Amount 列的数据来源）
  —— 不依赖浏览器的 API v2（该接口目前已被禁用），更稳更不受浏览器功能开关影响。
- 计算比例、判断阈值提醒
"""
import json
import os
from datetime import datetime

# Android 上使用 App 私有存储目录；桌面调试时退回到脚本所在目录
try:
    from android.storage import app_storage_path
    BASE_DIR = app_storage_path()
except Exception:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "monitor_config.json")
STATUS_PATH = os.path.join(BASE_DIR, "monitor_status.json")

# 默认监控地址：CGC/WGDC 的 DEX 交易对（V5 LP Pair）
DEFAULT_ADDRESS = "0x4575De99337ccd0A63BF4e20A33BFd776e40e215"

# GoodChain 链 RPC 节点（Chain ID 219）
DEFAULT_RPC_URL = "https://rpc1.goodchainscan.org/"

# 标准 Uniswap V2 / ERC20 函数选择器（函数签名 keccak256 前4字节），全网通用，无需改动
SEL_TOKEN0 = "0x0dfe1681"        # token0()
SEL_TOKEN1 = "0xd21220a7"        # token1()
SEL_GET_RESERVES = "0x0902f1ac"  # getReserves()
SEL_DECIMALS = "0x313ce567"      # decimals()
SEL_SYMBOL = "0x95d89b41"        # symbol()

DEFAULT_CONFIG = {
    "address": DEFAULT_ADDRESS,       # 要监控的 LP Pair 合约地址
    "rpc_url": DEFAULT_RPC_URL,       # 链的 RPC 节点地址
    "interval_minutes": 5,            # 刷新间隔（分钟）
    "tier2_low": 0.0,                 # 第2档：实时比例 低于 此值 -> 提醒“比例数低”
    "tier3_high": 0.0,                # 第3档：实时比例 高于 此值 -> 提醒“比例数高”
    "running": False,
}



def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = dict(DEFAULT_CONFIG)
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_status():
    if os.path.exists(STATUS_PATH):
        try:
            with open(STATUS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_status(status):
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def _eth_call(rpc_url, to_address, data_hex, timeout=15):
    """发一次 JSON-RPC eth_call，返回结果的十六进制字符串"""
    import requests

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to_address, "data": data_hex}, "latest"],
    }
    resp = requests.post(rpc_url, json=payload, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()
    if body.get("error"):
        raise RuntimeError(f"RPC错误: {body['error']}")
    result = body.get("result")
    if not result or result == "0x":
        raise RuntimeError("RPC返回空结果")
    return result


def _decode_address(hex_result):
    h = hex_result[2:] if hex_result.startswith("0x") else hex_result
    return "0x" + h[-40:]


def _decode_uint(hex_chunk):
    return int(hex_chunk, 16) if hex_chunk else 0


def _decode_string(hex_result):
    """解码标准 ABI 动态 string 返回值；解析失败则尝试当作 bytes32 处理"""
    h = hex_result[2:] if hex_result.startswith("0x") else hex_result
    try:
        length = int(h[64:128], 16)
        str_hex = h[128:128 + length * 2]
        return bytes.fromhex(str_hex).decode("utf-8", errors="ignore").strip()
    except Exception:
        try:
            raw = bytes.fromhex(h[:64])
            return raw.rstrip(b"\x00").decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""


def fetch_pair_info(rpc_url, pair_address, timeout=15):
    """
    读取 LP Pair 合约信息：token0/token1 地址、符号、精度、以及当前储备量(原始整数)。
    """
    token0_addr = _decode_address(_eth_call(rpc_url, pair_address, SEL_TOKEN0, timeout))
    token1_addr = _decode_address(_eth_call(rpc_url, pair_address, SEL_TOKEN1, timeout))

    reserves_hex = _eth_call(rpc_url, pair_address, SEL_GET_RESERVES, timeout)
    h = reserves_hex[2:] if reserves_hex.startswith("0x") else reserves_hex
    reserve0_raw = _decode_uint(h[0:64])
    reserve1_raw = _decode_uint(h[64:128])

    def _token_meta(addr):
        try:
            dec_hex = _eth_call(rpc_url, addr, SEL_DECIMALS, timeout)
            decimals = _decode_uint(dec_hex[2:] if dec_hex.startswith("0x") else dec_hex)
        except Exception:
            decimals = 18
        try:
            symbol = _decode_string(_eth_call(rpc_url, addr, SEL_SYMBOL, timeout))
        except Exception:
            symbol = ""
        return decimals, symbol

    t0_decimals, t0_symbol = _token_meta(token0_addr)
    t1_decimals, t1_symbol = _token_meta(token1_addr)

    return {
        "token0": {"address": token0_addr, "symbol": t0_symbol,
                   "decimals": t0_decimals, "reserve_raw": reserve0_raw},
        "token1": {"address": token1_addr, "symbol": t1_symbol,
                   "decimals": t1_decimals, "reserve_raw": reserve1_raw},
    }


def fetch_token_amounts(address, symbols=("CGC", "WGDC"), rpc_url=DEFAULT_RPC_URL, timeout=15):
    """
    通过链上 RPC 直接读取 DEX 交易对(LP Pair)的 CGC / WGDC 储备数量。
    返回 {symbol: amount(float)}，找不到的symbol值为 None。
    """
    result = {s: None for s in symbols}
    info = fetch_pair_info(rpc_url, address, timeout=timeout)

    for leg in (info["token0"], info["token1"]):
        sym = (leg["symbol"] or "").strip()
        for target in symbols:
            if sym.lower() == target.lower():
                result[target] = leg["reserve_raw"] / (10 ** leg["decimals"])

    return result


def compute_ratio(cgc_amount, wgdc_amount):
    """第1档比例 = CGC数量 / WGDC数量"""
    if not cgc_amount or not wgdc_amount:
        return None
    try:
        return cgc_amount / wgdc_amount
    except ZeroDivisionError:
        return None


def check_alert(ratio, tier2_low, tier3_high):
    """
    返回 'low' / 'high' / None
    低于第2档 -> low；高于第3档 -> high
    """
    if ratio is None:
        return None
    try:
        tier2_low = float(tier2_low or 0)
        tier3_high = float(tier3_high or 0)
    except (TypeError, ValueError):
        return None

    if tier2_low and ratio < tier2_low:
        return "low"
    if tier3_high and ratio > tier3_high:
        return "high"
    return None


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
