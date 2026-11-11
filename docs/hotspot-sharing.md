> 历史记录：此文档描述 2026-10-18 测试版；1.0.0 的使用和构建以根目录 README.md 为准。

# Clash Meta Hotspot 本地修改版

## 使用

1. 安装 APK（ARM64，包名 `com.github.metacubex.clash.hotspot`，应用名 Clash Meta Hotspot）。独立签名和包名，可与官方版并存；首次使用需导入自己的订阅或配置。
2. 先关闭手机热点，进入「设置 → 网络」，保持「路由系统流量」开启，开启「热点共享 VPN（root）」。热点接口先留空，默认自动识别。
3. 返回主页启动 Clash VPN，在 Magisk/KernelSU 等 root 管理器中允许本应用执行 root。
4. 开启手机系统热点，再连接其他设备；连接设备无需设置 HTTP/SOCKS 代理。
5. 在「设置 → 网络 → 热点共享状态」查看规则安装状态。用连接设备检查网站访问、出口 IP 和 DNS，确认确实遵循所选 Clash 策略。
6. 改变共享选项前停止 VPN。停止 VPN 会移除本次共享规则并恢复系统普通热点路由，连接设备随后可能通过运营商直接上网。

## 边界

- 仅共享 IPv4；启用共享时阻止被识别热点接口的 IPv6 转发。手机自身 IPv6 设置保持原有逻辑。
- 流量遵循当前 Clash 规则。若要求所有连接设备流量走代理，请在 Clash 中选择全局代理；规则里的 DIRECT 仍会直连。
- 使用系统热点设置开启/关闭热点；首次授权后若热点之前已开，须关闭再开启，使停用硬件卸载生效。
- 无 root、root 被拒绝、内核不支持所需 iptables/ip6tables 或 OEM 限制时，共享无法启用；可在共享状态和应用日志中查看原因。
- 自动识别依据系统 tethering dump。OEM 格式不同可填实际热点接口名（例如 wlan1、ap0），不能把上游移动网络/Wi-Fi 接口当作热点接口。
- VPN 运行期间，root 进程通过服务 PID 和会话文件监控退出，正常停止、应用进程退出后清理自有规则。若 root 进程被强制 SIGKILL，重启手机清理残留内核规则。
- 此功能不提供 VPN 停止后的断网锁。不要把「规则已启用」当作连接设备已通过验证。

## 源码与构建

- 上游：https://github.com/MetaCubeX/ClashMetaForAndroid
- 本次基线：main `3cc102aab3f251ef460a3b6e2835b6c1eb581e73`（2026-10-18 拉取，最新稳定版 2.11.35 之后的主分支）。
- 核心子模块：`88dcbf7f1614a67c3b36b848ee3592dfa92ada36`。
- 本地分支：`codex/hotspot-vpn-share`。
- JDK 21、Android SDK 35、NDK 29.0.14206865、Gradle 8.10.2。按上游 CI 使用 MetaCubeX Go 1.26（本次工具链输出 go1.26.9），并应用 `.github/patch/*.patch`。
- `local.properties` 指定 SDK、`custom.application.id=com.github.metacubex.clash.hotspot`、`remove.suffix=true`。
- `signing.properties` 的 `keystore.path` 指定私有本地密钥（密钥和密码均已忽略，不应提交）。未来覆盖安装本修改版须保留此密钥。

```sh
python3 -m unittest discover -s tests -v
JAVA_HOME=/opt/homebrew/opt/openjdk@21 \
PATH="$PWD/.toolchains/go/bin:/opt/homebrew/opt/openjdk@21/bin:$PATH" \
GOTOOLCHAIN=local GOPROXY=https://goproxy.cn,https://proxy.golang.org,direct \
./gradlew --no-daemon :app:assembleMetaRelease -PtargetAbis=arm64-v8a --max-workers=4 -x :app:downloadGeoFiles
```

上述跳过下载任务只适用于已准备好 `app/src/main/assets/` 中 geoip.metadb、geosite.dat、ASN.mmdb、BundleMRS.7z 的情况。本次通过 curl 从上游 meta-rules-dat release 下载，替代 Java 下载任务的 TLS 握手失败。正常联网构建可去掉 `-x :app:downloadGeoFiles`。

## 验证记录

- 4 项脚本模拟测试通过：Android 10/新版本路由优先级、DNS/IPv6 规则与停止清理、root 拒绝、部分安装失败回滚。
- 模拟命令测试不能证明 Android 内核转发或 OEM 热点兼容性；具体 APK 构建与模拟器检查见交付目录的验证记录。
- 当前未连接实体手机，尚未验证真实热点客户端的出口 IP、DNS、TCP/UDP 或 OEM 硬件转发行为。
