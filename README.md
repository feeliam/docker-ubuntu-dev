# docker-ubuntu-dev

Ubuntu 18.04、20.04、22.04 开发基础镜像，提供普通版、浏览器桌面版、ROS 普通版和 ROS 桌面版。每种均有 amd64、arm64 独立 Dockerfile、入口脚本和使用文档，共 **24 个镜像**。

全部预装 `build-essential`、`gcc`、`g++`、`gdb`、`vim`、`openssh-server`、Python 3、pip3 和 Python 开发头文件。桌面版增加精简 MATE、Firefox、TigerVNC 和 noVNC，浏览器打开网页即可操作容器桌面。

**默认用户名、SSH 密码和 VNC 密码均为 `ubuntu`。** sudo 使用用户密码。默认示例仅监听宿主机本地地址，对外使用前修改密码。

## 快速开始

需要 Docker Engine/Desktop、Buildx。便捷运行和测试脚本另外需要宿主机 Python 3，测试需要 OpenSSH 客户端。以下从仓库根目录执行：

```bash
./scripts/build.sh --ubuntu 22.04 --variant base --arch arm64
./scripts/run.sh --ubuntu 22.04 --variant base --arch arm64
```

该普通版通过 SSH 和容器终端使用：

```bash
ssh ubuntu@localhost -p 2222
docker exec -it --user ubuntu ubuntu-dev-2204-base-arm64 bash
```

Intel/AMD 主机将 `--arch arm64` 改成 `--arch amd64`，对应容器名也改为 amd64。Apple Silicon/常见 ARM 服务器使用 arm64。跨架构构建和运行需要原生节点或 QEMU，Docker Desktop 通常自带模拟支持，可用 `docker buildx ls` 检查。

需要浏览器桌面和 ROS Humble 时，另外构建、启动对应变体；使用不同端口即可与普通版同时运行：

```bash
./scripts/build.sh --ubuntu 22.04 --variant desktop-ros --arch arm64
./scripts/run.sh --ubuntu 22.04 --variant desktop-ros --arch arm64 --ssh-port 2223
```

打开 **http://localhost:6080/vnc.html?resize=remote**，连接密码为 `ubuntu`。桌面中可打开 Firefox。

按本次要求，仅对 **22.04 base arm64** 完成最终构建和运行验收；其他变体提供完整文件及文档，尚未完成最终运行验收。详见 [验证记录](docs/validation.md)。

普通命令行镜像：

```bash
./scripts/build.sh --ubuntu 20.04 --variant base --arch amd64
./scripts/run.sh --ubuntu 20.04 --variant base --arch amd64 --name focal-dev --ssh-port 2224
ssh ubuntu@localhost -p 2224
```

## 镜像矩阵

每个架构目录均可独立复制和构建。以下链接包含该镜像完整的构建、启动、连接、开发和清理命令。

| Ubuntu | 类型 | 使用文档 |
|---|---|---|
| 18.04 | base | [amd64](ubuntu1804/amd64/README.md) / [arm64](ubuntu1804/arm64/README.md) |
| 18.04 | desktop | [amd64](ubuntu1804-desktop/amd64/README.md) / [arm64](ubuntu1804-desktop/arm64/README.md) |
| 18.04 | ros | [amd64](ubuntu1804-ros/amd64/README.md) / [arm64](ubuntu1804-ros/arm64/README.md) |
| 18.04 | desktop-ros | [amd64](ubuntu1804-desktop-ros/amd64/README.md) / [arm64](ubuntu1804-desktop-ros/arm64/README.md) |
| 20.04 | base | [amd64](ubuntu2004/amd64/README.md) / [arm64](ubuntu2004/arm64/README.md) |
| 20.04 | desktop | [amd64](ubuntu2004-desktop/amd64/README.md) / [arm64](ubuntu2004-desktop/arm64/README.md) |
| 20.04 | ros | [amd64](ubuntu2004-ros/amd64/README.md) / [arm64](ubuntu2004-ros/arm64/README.md) |
| 20.04 | desktop-ros | [amd64](ubuntu2004-desktop-ros/amd64/README.md) / [arm64](ubuntu2004-desktop-ros/arm64/README.md) |
| 22.04 | base | [amd64](ubuntu2204/amd64/README.md) / [arm64](ubuntu2204/arm64/README.md) |
| 22.04 | desktop | [amd64](ubuntu2204-desktop/amd64/README.md) / [arm64](ubuntu2204-desktop/arm64/README.md) |
| 22.04 | ros | [amd64](ubuntu2204-ros/amd64/README.md) / [arm64](ubuntu2204-ros/arm64/README.md) |
| 22.04 | desktop-ros | [amd64](ubuntu2204-desktop-ros/amd64/README.md) / [arm64](ubuntu2204-desktop-ros/arm64/README.md) |

标签统一为 `ubuntu-dev:<版本>-<类型>-<架构>`，例如 `ubuntu-dev:18.04-desktop-ros-amd64`。镜像在本地构建，不自动推送到镜像仓库。

| Ubuntu | ROS 普通版 | ROS 桌面版 | `python` 命令 |
|---|---|---|---|
| 18.04 | Melodic ros-base | Melodic desktop | 非 ROS 镜像为 Python 3；Melodic 为 Python 2.7，另有 Python 3 |
| 20.04 | Noetic ros-base | Noetic desktop | Python 3 |
| 22.04 | Humble ros-base | Humble desktop | Python 3 |

## 脚本参数

三个脚本均支持 `--help` 和以下镜像选择参数：

| 参数 | 取值 | 默认值 |
|---|---|---|
| `--ubuntu` | `18.04`、`20.04`、`22.04` | `22.04` |
| `--variant` | `base`、`desktop`、`ros`、`desktop-ros` | `base` |
| `--arch` | `amd64`、`arm64` | 宿主机架构 |

`build.sh` 使用 `docker buildx build --platform ... --load` 构建到本地 Docker。`run.sh` 额外支持：

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--name` | 容器名 | `ubuntu-dev-<无点版本>-<类型>-<架构>` |
| `--ssh-port` | 宿主机 SSH 端口 | `2222` |
| `--web-port` | 宿主机网页端口 | `6080`，仅桌面版 |
| `--bind` | IPv4 监听地址 | `127.0.0.1`，局域网用 `0.0.0.0` |
| `--workspace` | 挂载至 `/workspace` 的现有宿主机目录 | 不挂载 |
| `--home-volume` | 保存 `/home/<用户>` 的 Docker 命名卷 | 不挂载 |

运行脚本默认后台启动，桌面版自动设置 `--shm-size=512m`。脚本检测名称、端口冲突，不替换已有容器。

```bash
mkdir -p "$PWD/workspace"
CONTAINER_USER=developer CONTAINER_PASSWORD=devpassword \
VNC_PASSWORD=vncpass VNC_GEOMETRY=1600x900 \
  ./scripts/run.sh --ubuntu 22.04 --variant desktop-ros --arch arm64 \
  --name ros-dev --ssh-port 2223 --web-port 6081 \
  --workspace "$PWD/workspace" --home-volume ros-dev-home
```

访问 `http://localhost:6081/vnc.html?resize=remote`，VNC 密码为 `vncpass`；SSH 使用 `ssh developer@localhost -p 2223`。原生 Docker 的变量是 `USER`、`PASSWORD`、`VNC_PASSWORD`、`VNC_GEOMETRY`。脚本用 `CONTAINER_*` 避免误传宿主机 `$USER`，详见 [运行配置](docs/usage.md)。

`smoke-test.sh` 额外支持 `--all`（覆盖选择参数，检查全部 24 组）和 `--skip-build`（使用本地镜像）：

```bash
./scripts/smoke-test.sh --ubuntu 22.04 --variant desktop-ros --arch arm64
./scripts/smoke-test.sh --all
./scripts/smoke-test.sh --all --skip-build
```

测试只清理自身创建的临时容器和卷，保留镜像。原始日志、JSON 汇总位于不提交的 `.test-results/`；实际执行结果见 [验证记录](docs/validation.md)。

## 运行机制与维护

入口初始化普通用户和独立 SSH 主机密钥，再启动 SSH 或桌面服务。Supervisor 管理桌面服务，Tini 负责信号转发和子进程回收；noVNC 将浏览器连接转为容器内 TigerVNC 会话。默认不暴露原生 VNC 端口，网页不写入密码。传统 VNC 认证仅使用密码前 8 字节。

ROS 环境在入口和 Shell 初始化中加载；非交互 `docker exec` 使用 `bash -lc`。18.04 Firefox 使用发行版兼容 DEB，20.04/22.04 使用 Mozilla 官方 DEB，不依赖 Snap。

- [运行配置、持久化、公钥与局域网](docs/usage.md)
- [ROS 工作空间、发布订阅、RViz 和网络](docs/ros.md)
- [构建、桌面、端口与软件源排错](docs/troubleshooting.md)
- [实际验证记录](docs/validation.md)

构建文件与对应文档由 `scripts/generate.py` 统一生成。修改生成逻辑或入口模板后执行：

```bash
python3 scripts/generate.py
python3 scripts/generate.py --check
python3 -m unittest discover -s tests -v
```

桌面机制参考 [Tiryoh/docker-ros2-desktop-vnc](https://github.com/Tiryoh/docker-ros2-desktop-vnc)，ROS 软件源参考 [官方 ROS Dockerfiles](https://github.com/osrf/docker_images)。项目代码采用 [MIT License](LICENSE)，镜像内软件遵循各自许可证。
