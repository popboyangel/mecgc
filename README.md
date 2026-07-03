# CGC / WGDC 比例监控 App

一个安卓后台监控小工具，定时直接从 GoodChain 链的 RPC 节点读取
DEX 交易对地址 `0x4575De99337ccd0A63BF4e20A33BFd776e40e215` 里
**CGC** 和 **WGDC** 的储备数量，计算 `CGC数量 / WGDC数量` 比例，
超出你设定的阈值就发系统通知提醒。

## 数据来源说明（重要更新）

一开始设计是调用 goodchainscan.org 浏览器的 API v2，但实测发现该浏览器
把 API v2 关闭了（返回 `{"message":"API V2 is disabled"}`）。

现在改为**直接对链上 RPC 节点发请求**，不走浏览器：

- 你监控的这个地址本身就是一个 DEX 交易对合约（LP Pair），
  它自带标准接口 `getReserves()`，直接返回两个代币的储备量——
  这正是浏览器 tokens 页面 "Amount" 那一栏显示数字的来源。
- 程序会先调用 `token0()` / `token1()` 拿到两个代币各自的合约地址，
  再各自调用 `symbol()` 和 `decimals()` 确认哪个是 CGC、哪个是
  WGDC，最后用 `getReserves()` 读到的原始整数除以精度得到实际数量。
- 好处：完全不依赖浏览器功能开关，只要 RPC 节点（`rpc1.goodchainscan.org`）
  能访问就行，更稳定。

## 三个需求对应实现

1. **定时刷新** —— 后台服务 `service.py` 按你设置的分钟数循环，对 RPC 节点
   发 `eth_call` 读取 Pair 合约的储备量。
2. **三档比例 + 阈值提醒** —— 界面里可设置：
   - 第1档：程序自动算出的**实时比例**（不用你填）
   - 第2档：你填的下限，实时比例 **低于** 它 → 通知「提示我现在比例数低！」
   - 第3档：你填的上限，实时比例 **高于** 它 → 通知「提示我现在比例数高！」
3. **后台长期运行** —— 用 Android **前台服务**（Foreground Service）+
   持久通知栏图标实现，息屏也能继续跑（需要你手动给一次
   「后台运行」和「电池优化白名单」权限，见下方"安装后必做"）。

## ⚠️ 重要说明：我没法在这里帮你直接编译出 APK

我这边是一个没有 Android SDK/NDK、且网络受限的沙箱环境，无法本地编译安卓安装包。
但我已经把 **完整可运行的源代码 + 打包配置 + 自动化编译脚本** 都写好了，
你只需要"云端点一下"，全程不用装 Android Studio、不用配环境。步骤如下：

### 第一步：先在电脑上测试取数逻辑（强烈建议，见下一节）

在传去 GitHub 编译之前，先确认能不能正确取到数据，避免白等半小时编译。

### 第二步：把代码传到 GitHub（免费）

1. 打开 https://github.com ，注册/登录账号。
2. 新建一个仓库（Repository），比如叫 `cgcmonitor`。
3. 把本项目里的所有文件上传到这个仓库（网页拖拽上传或 `git push` 都可以）。

### 第三步：等 GitHub 自动编译

- 文件传上去后会自动触发 `.github/workflows/build.yml` 里的编译流程。
- 打开仓库的 **Actions** 标签页，第一次编译大约需要 15~30 分钟。

### 第四步：下载 APK 安装

- 编译成功后，进入该次运行详情页 → **Artifacts** 区域下载 `cgcmonitor-apk`，
  解压出 `.apk`，传到手机上安装（需允许"安装未知来源应用"）。

### 安装后必做（否则息屏后台会被系统杀掉）

- 手机「设置 → 电池 → App 电量管理」把本 App 设为 **不限制/无限制**。
- 打开 App 后同意「通知权限」。
- 首次进入填好 **刷新间隔**、**第2档**、**第3档**，点「保存并启动监控」。

## 本地先测试取数逻辑（推荐，几秒钟出结果）

```bash
pip install requests
python test_api.py
```

会打印出 token0/token1 的地址、symbol、decimals，以及最终算出的
CGC、WGDC 数量和比例。如果失败会有中文提示，把报错发给我即可。

### 如果 test_api.py 也失败，最快的排查方式

用命令行直接测一下 RPC 节点通不通（这条命令查询 token0()）：

```bash
curl -X POST https://rpc1.goodchainscan.org/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":"0x4575De99337ccd0A63BF4e20A33BFd776e40e215","data":"0x0dfe1681"},"latest"]}'
```

正常应该返回类似 `{"jsonrpc":"2.0","id":1,"result":"0x000...(一串十六进制)"}`。
如果报错或者连不上，可能是 RPC 地址需要调整（比如加端口号），
把返回结果发给我，我来帮你改。

## 本地想先在电脑上试跑界面（可选）

```bash
pip install kivy requests plyer
python main.py
```
（桌面上后台服务和系统通知走的是兜底逻辑，只用来验证界面和取数逻辑是否正常，
真正的后台常驻能力只在安卓设备上生效。）
