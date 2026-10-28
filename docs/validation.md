# 验证记录

验证日期：2026-10-28（Asia/Shanghai）。根据最终要求，仅对 **Ubuntu 22.04 / base / arm64** 完成本轮构建及运行验收，其余镜像维护 Dockerfile、入口脚本、使用文档和测试接口，不继续构建。

## 实际构建与运行

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

其余 23 个组合未完成最终运行验收。MATE/noVNC、Firefox、ROS 工作空间和通信、RViz、amd64 模拟运行均不列为已通过。

在范围收窄前曾完成 18.04 base arm64 的早期构建测试，并启动 22.04 桌面 arm64、base amd64 构建；后两者已按要求取消，早期结果不代替当前文件的最终验收。

后续已定向清理上述构建残留：删除 18.04 早期镜像、旧的无标签镜像，以及约 1.338 GB 无需保留的 BuildKit 缓存。保留最终的 `ubuntu-dev:22.04-base-arm64` 及其约 502.7 MB 共享构建缓存；原有镜像和容器保留，测试容器与测试卷均已清理。

后续需要验证其他镜像时，使用对应 README 的单镜像命令；只有明确需要完整矩阵时才运行 `./scripts/smoke-test.sh --all`。
