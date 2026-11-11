# Clash-Meta-Hotspot

基于 **MetaCubeX/ClashMetaForAndroid** 的非官方 Android 修改版，面向已 root 手机，研究将 Clash VPN 网络共享给手机热点连接设备的实现。项目名称为 `Clash-Meta-Hotspot`；应用安装名称为 **Clash Meta Hotspot**。

当前项目版本：**1.0.1**。本项目版本独立于上游版本，1.0.0 并不代表上游 Clash Meta 的版本。

## 上游来源与致谢

- 直接上游：[MetaCubeX/ClashMetaForAndroid](https://github.com/MetaCubeX/ClashMetaForAndroid)，Android 界面、VPN 服务、配置管理与主要应用代码均来自该项目。
- 本版同步上游 `main`，提交 `215e017ae88ac2a1edf24fdb520512c1423c89f4`，对应上游 **2.11.37**，同步日期 2026-11-12。
- 核心：[MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo)，子模块固定于 `0455d0d28c4526937380505153e65a843d8612e8`。
- 项目历史中的 Clash for Android / Kr328 及其他原作者贡献、版权声明和许可证继续保留。
- 原始上游 README 保存在 [docs/UPSTREAM-README.md](docs/UPSTREAM-README.md)。第三方依赖以对应模块自带许可证为准。

本仓库是个人维护的衍生项目，不是 MetaCubeX、Clash Meta、mihomo 或 Kr328 的官方发行版，也不代表上述维护者。感谢原作者和社区的持续贡献；本项目只对自己的增量修改负责，不将上游成果宣称为原创。

## 1.0.1 界面优化

首页共享入口改为与现有卡片相同的圆角、阴影、图标对齐与文字样式；使用 Material 开关，支持点击整张卡片切换。状态文案按系统语言显示，详细诊断仍在网络设置中查看。

## 1.0.0 修改范围

- 首页增加「热点共享 VPN（root）」开关与状态文字。
- VPN 运行时可直接开启、关闭共享；共享关闭会清理自己的规则，不要求重启整个 VPN。
- 识别本应用的 VPN 接口，自动查找系统热点下游接口，支持手动指定接口。
- 为热点 IPv4 客户端配置路由、NAT 和 TCP/UDP DNS 转发；共享流量遵循当前 Clash 策略。
- 共享期间阻止所识别下游接口的 IPv6 转发，避免在只实现 IPv4 共享时通过 IPv6 绕过。
- root 拒绝、命令失败、共享停止和会话退出有对应状态与清理逻辑。
- 保留独立包名和签名，与官方安装并存。

## 下载与安装

从本仓库 [Releases](https://github.com/fengnanrui/Clash-Meta-Hotspot/releases) 下载 `v1.0.1` 的 ARM64 APK。包名为 `com.github.metacubex.clash.hotspot`；本版仅发布 `arm64-v8a`。

首次安装需要自行导入合法获得的订阅或配置。本项目不提供代理节点、账号、订阅服务或网络接入承诺。请保留原应用配置备份，两个应用的数据不会自动互通。系统同一时间通常只能使用一个 VPN 服务，使用本修改版前应停止其他 VPN 应用。

## 使用步骤

1. 准备支持 root 的 Android 手机，并确认 root 管理器正常工作。
2. 先关闭系统热点；导入配置，确认本手机使用 Clash VPN 可以联网。
3. 在首页打开「热点共享 VPN（root）」。若 VPN 尚未运行，启动 VPN；在 root 管理器提示中授予本应用权限。
4. 开启 Android 系统热点，让另一台设备连接；连接设备无需手动填写 HTTP/SOCKS 代理。
5. 查看首页共享状态，再用连接设备访问网站、检查出口 IP 和 DNS，验证实际联网路径。
6. 运行时关闭首页共享开关会清理共享规则。关闭整个 VPN 也会结束共享。

如果热点在启用共享之前已经开启，请关闭并重新打开热点，以使硬件卸载设置生效。默认自动识别热点接口；识别失败时，到「设置 → 网络 → 热点接口」填写实际接口名，例如 `wlan1` 或 `ap0`。不要猜测接口，更不要误填上游移动网络接口；不同厂商名称不同。修改接口前先关闭共享，修改后重新开启。

## 必须理解的行为

共享遵循 Clash 当前规则：规则模式中的 DIRECT 仍会直连；如需所有受支持流量走代理，请自行选择全局代理和可用节点。当前实现只共享 IPv4，不提供完整 IPv6 共享。

**关闭共享或停止 VPN 后恢复系统普通热点网络，设备可能直接通过运营商上网；本项目没有 VPN 停止后的断网锁。**「规则已启用」仅表示命令执行完成，不代表连接设备已通过实际联网验收。

不同 Android 版本、内核、SELinux、root 实现、厂商热点与硬件/BPF 卸载可能影响效果。出现问题时先关闭共享，查看首页状态和应用日志。若 root 进程被强制杀死导致残留规则，可重启手机恢复；不要执行清空系统所有防火墙规则之类的广泛操作。

## 验证边界

发布附件中的验证记录列出本次实际执行的检查。脚本模拟测试、编译、签名检查和模拟器安装可以发现实现问题，但不能替代真实手机热点客户端的 TCP/UDP、DNS、出口 IP 及切换测试。不声明适配所有 root 设备；未经实际验证的设备保持未验证状态。

## 源码构建

```sh
git clone --recurse-submodules https://github.com/fengnanrui/Clash-Meta-Hotspot.git
cd Clash-Meta-Hotspot
git checkout v1.0.1
git submodule update --init --recursive
```

使用 JDK 21、Android SDK 35、NDK 29.0.14206865、仓库 Gradle wrapper；Go 使用上游 CI 指定的 MetaCubeX Go 1.26，并应用 `.github/patch/` 下补丁。`local.properties` 示例：

```properties
sdk.dir=/your/android/sdk
custom.application.id=com.github.metacubex.clash.hotspot
remove.suffix=true
```

自行生成签名密钥，并在本地 `signing.properties` 填写 `keystore.path`、`keystore.password`、`key.alias`、`key.password`。不要提交密钥或密码。发布 APK 使用维护者私有签名，自己构建的不同签名 APK 不能直接覆盖安装发布包。

```sh
python3 -m unittest discover -s tests -v
./gradlew :app:assembleMetaRelease -PtargetAbis=arm64-v8a
```

构建需要下载 Go/Maven 依赖和 geo 数据。仅在已准备好四个 geo 数据文件时，才可用 `-x :app:downloadGeoFiles` 跳过下载。版本显示为 1.0.1，内部 versionCode 保持递增以支持覆盖前期测试包。构建细节参见源代码，旧实验版说明仅作为历史记录。

## 许可证与再分发

本项目遵循上游 **GNU General Public License version 3（GPLv3）**，完整条款见 [LICENSE](LICENSE)。原作者版权与归属保留；本仓库的增量修改按同一许可证提供。第三方组件可能有自己的许可证，应一并遵守。

修改和再分发时请保留版权、许可证和必要声明，说明修改内容，并履行适用的对应源代码提供义务。APK 发布同时提供源码标签和源码附件，子模块固定提交可供核对。README 的用途说明不会替代、缩减或附加限制于 GPL 已授予的权利；具体权利义务以完整许可证为准。

## 学习参考与责任说明

本项目主要用于学习、技术研究与参考，包括理解 Android VpnService、Linux 路由、防火墙、DNS 和热点共享机制。请仅在自己拥有或获授权管理的设备、网络和测试环境中使用，遵守所在地适用法律、网络使用规则及服务条款。

不得将本项目用于未经授权的网络访问、侵害他人隐私或其他违法活动。请自行评估 root 权限、网络配置变更、流量成本以及设备稳定性影响，不向不可信来源提供订阅凭据。提交问题时请删除节点密码、token、订阅链接和个人信息。

软件按 GPL 中的「现状」与免责条款提供，不保证适销性、特定用途适用性、持续可用或与所有设备兼容。学习参考声明不是对所有使用后果的保证，也不免除依法不可免除的责任。请以实际测试和许可证原文为准。

上游 GitHub Actions 工作流归档在 `docs/upstream-workflows/` 供参考，避免新仓库自动执行上游专用的版本更新或发布操作。

本次发布构建实际使用本机已有 Gradle 8.11.1（上游 wrapper 为 8.10.2），保留上游 wrapper 配置；Geo 数据沿用 2026-10-18 已下载文件，核心与应用代码同步至上述最新提交。
