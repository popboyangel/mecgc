# -*- coding: utf-8 -*-
"""
test_api.py
在电脑上快速验证：能否直接从链上 RPC 节点正确读到 CGC / WGDC 的储备数量并算出比例。
不需要安卓环境，不需要 Kivy，只需要 requests。

用法：
    pip install requests
    python test_api.py
"""
from monitor_core import (
    fetch_pair_info, fetch_token_amounts, compute_ratio,
    DEFAULT_ADDRESS, DEFAULT_RPC_URL,
)

if __name__ == "__main__":
    print("RPC节点  :", DEFAULT_RPC_URL)
    print("Pair地址 :", DEFAULT_ADDRESS)
    print("-" * 40)

    try:
        info = fetch_pair_info(DEFAULT_RPC_URL, DEFAULT_ADDRESS)
        print("token0:", info["token0"])
        print("token1:", info["token1"])
    except Exception as e:
        print(f"失败：读取 Pair 信息出错：{e}")
        print("请检查 RPC 节点地址是否正确（比如是否需要加端口/路径），"
              "或者把上面的报错发给我看看。")
        raise SystemExit(1)

    print("-" * 40)
    amounts = fetch_token_amounts(DEFAULT_ADDRESS, symbols=("CGC", "WGDC"), rpc_url=DEFAULT_RPC_URL)
    cgc = amounts.get("CGC")
    wgdc = amounts.get("WGDC")
    ratio = compute_ratio(cgc, wgdc)

    print(f"CGC 数量  : {cgc}")
    print(f"WGDC 数量 : {wgdc}")
    print(f"比例 CGC/WGDC : {ratio}")

    if cgc is None or wgdc is None:
        print("\n有一个代币没匹配到符号，可能 token0/token1 的 symbol() 返回和预期不一致，"
              "把上面打印的 token0/token1 原始信息发给我，我来调整解析逻辑。")
    else:
        print("\n取数成功，逻辑正常，可以放心去打包 APK 了。")
