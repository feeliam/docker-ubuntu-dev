# 验证记录

最新验证日期：2026-11-08（Asia/Shanghai）。已验证 **Ubuntu 18.04 / desktop-ros / arm64**；保留此前 2026-10-28 的 **Ubuntu 22.04 / base / arm64** 验收记录。

## 2026-11-08：18.04 / desktop-ros / arm64

镜像：`ubuntu-dev:18.04-desktop-ros-arm64`，平台 `linux/arm64`，镜像 ID：`sha256:a9d181339f130e96ff4c98ec096c80ec71bb31b415057af0c79134603c54e937`。

原始构建遇到 HTTP 502 和 GitHub TLS/连接故障。本轮使用 `.test-results/18.04-desktop-ros-arm64-build/` 临时上下文：Ubuntu 软件源切换至中科大 HTTPS 镜像，以宿主机可信 CA 引导；Tini 预先下载并核对仓库固定 SHA-256；rosdep 默认源列表通过 GitHub 官方 API 获取并校验 Git blob 标识；ROS 软件包仍来自官方 Melodic 最终快照并保留签名校验。构建期间使用的本机临时转发已关闭。此结果验证该镜像的运行功能，不代表原始下载通路已恢复。

同步修复生成脚本中 Bionic GPG 不支持 `--show-keys` 的问题，并将 ROS Bash 初始化移至交互判断之前，使非交互 SSH 命令也能加载 ROS。桌面验收补充 WebSocket `binary` 子协议，Firefox 改用本地 HTML 测试页。

```bash
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  ./scripts/smoke-test.sh --ubuntu 18.04 --variant desktop-ros --arch arm64 --skip-build
```

结果：**PASS**，共 11 组检查。涵盖架构、密码/公钥 SSH、编译工具、Python、sudo、ROS 工作空间编译与消息发布订阅、MATE/noVNC/WebSocket/VNC 密码认证、Firefox 和 RViz 窗口、重启持久化、自定义用户与绑定目录、独立 SSH 主机密钥以及命令退出码。测试容器和卷已清理，保留镜像。

构建日志为 `.test-results/18.04-desktop-ros-arm64-build.log`，运行日志为 `.test-results/18.04-desktop-ros-arm64.log`，汇总为 `.test-results/summary.json`。24 组生成文件一致性、现有 8 项单元检查和 `git diff --check` 均通过。

## 2026-10-28：22.04 / base / arm64

镜像：`ubuntu-dev:22.04-base-arm64`。构建平台为 Docker Desktop Linux arm64。

```bash
./scripts/smoke-test.sh --ubuntu 22.04 --variant base --arch arm64
```

结果：**PASS**。

| 检查 | 结果 |
|---|---|
| 从最终 Dockerfile 构建、系统版本及 arm64 架构 | 通过 |
| 默认用户/密码 SSH 登录 | 通过 |
| gcc/g++ 编译并运行 C/C++，gdb、vim、sshd、Python/pip 检查 | 通过 |
| sudo 密码验证、SSH 公钥登录、禁止 root 登录配置 | 通过 |
| 停止并再次启动，主目录卷中文件及 SSH 主机密钥保留 | 通过 |
| 自定义用户名/密码 SSH 登录、绑定目录写入 | 通过 |
| 不同容器使用独立 SSH 主机密钥 | 通过 |
| 自定义命令以普通用户执行并传递退出码 | 通过 |

测试完成后清理测试创建的容器和卷，保留构建镜像。测试实现见 [`smoke.py`](../scripts/smoke.py)，原始结果见本地 `.test-results/summary.json`，日志见 `.test-results/22.04-base-arm64.log`；这些运行产物不提交版本库。

## 全部文件的静态检查

24 个架构目录均已检查生成结果一致性；README 相对链接、代码块 Shell 语法、脚本参数和构建目录选择通过自动检查。CLI 检查覆盖 24 种组合，以及无效参数、同名容器、端口占用、重复端口、宿主机用户名隔离和启动失败清理。

```bash
python3 scripts/generate.py --check
python3 -m unittest discover -s tests -v
git diff --check
```

单元检查共 8 项，全部通过。涉及端口的检查需要允许绑定临时 localhost 端口。

## 验收边界

除上述两个组合外，其余 22 个组合未完成最终运行验收。MATE/noVNC、Firefox、ROS 工作空间和通信、RViz 仅在 18.04 desktop-ros arm64 完成验证；其他组合及 amd64 模拟运行不列为已通过。

在范围收窄前曾完成 18.04 base arm64 的早期构建测试，并启动 22.04 桌面 arm64、base amd64 构建；后两者已按要求取消，早期结果不代替当前文件的最终验收。

后续已定向清理上述构建残留：删除 18.04 早期镜像、旧的无标签镜像，以及约 1.338 GB 无需保留的 BuildKit 缓存。保留最终的 `ubuntu-dev:22.04-base-arm64` 及其约 502.7 MB 共享构建缓存；原有镜像和容器保留，测试容器与测试卷均已清理。

后续需要验证其他镜像时，使用对应 README 的单镜像命令；只有明确需要完整矩阵时才运行 `./scripts/smoke-test.sh --all`。
