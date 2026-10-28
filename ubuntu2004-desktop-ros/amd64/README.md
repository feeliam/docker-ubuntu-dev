# Ubuntu 20.04 / desktop-ros / amd64

[返回总览](../../README.md) · [机制与配置](../../docs/usage.md) · [排错](../../docs/troubleshooting.md) · [ROS 开发](../../docs/ros.md)

镜像：`ubuntu-dev:20.04-desktop-ros-amd64`；默认容器名：`ubuntu-dev-2004-desktop-ros-amd64`。默认用户/SSH 密码：`ubuntu` / `ubuntu`，sudo 使用同一密码。`python` 为 系统 Python 3。
包含精简 MATE、Firefox、TigerVNC 和 noVNC。 ROS 发行版为 **noetic**，预装 **desktop**。

## 构建

以下命令均从仓库根目录执行。需要 Docker Engine/Desktop、Buildx；跨架构构建/运行需要原生节点或 QEMU（Docker Desktop 通常已配置）。目录名不能代替 `--platform`。

```bash
docker buildx build --platform linux/amd64 --load \
  -t ubuntu-dev:20.04-desktop-ros-amd64 ./ubuntu2004-desktop-ros/amd64
# 或使用脚本
./scripts/build.sh --ubuntu 20.04 --variant desktop-ros --arch amd64
```

此目录可单独复制：进入目录后执行 `docker buildx build --platform linux/amd64 --load -t ubuntu-dev:20.04-desktop-ros-amd64 .`。

## 启动和连接

```bash
docker run -d --platform linux/amd64 --name ubuntu-dev-2004-desktop-ros-amd64 \
  -p 127.0.0.1:2222:22 \
  -p 127.0.0.1:6080:80 --shm-size=512m \
  -e USER=ubuntu -e PASSWORD=ubuntu \
  ubuntu-dev:20.04-desktop-ros-amd64
# 或使用脚本（二选一，不能用同名容器重复启动）
./scripts/run.sh --ubuntu 20.04 --variant desktop-ros --arch amd64

ssh ubuntu@localhost -p 2222
docker exec -it --user ubuntu ubuntu-dev-2004-desktop-ros-amd64 bash
```

浏览器打开 **http://localhost:6080/vnc.html?resize=remote**，点击连接，VNC 密码默认 `ubuntu`。桌面已经自动启动，无需在容器内手工启动。
在桌面菜单中打开 Firefox 或终端执行 `firefox`；也可从宿主机启动：

```bash
docker exec --user ubuntu -e HOME=/home/ubuntu -e DISPLAY=:1 ubuntu-dev-2004-desktop-ros-amd64 firefox --new-window about:blank
```

VNC 使用传统密码认证，仅前 8 字节有效；可通过 `VNC_PASSWORD` 单独设置。网页不会自动填入或保存密码。

## 自定义与持久化

下面创建另一个容器，使用独立端口、工作目录挂载和命名用户目录卷。`CONTAINER_*` 是宿主机脚本变量，原生 Docker 对应 `USER`、`PASSWORD`。

```bash
mkdir -p "$PWD/workspace"
CONTAINER_USER=developer CONTAINER_PASSWORD=devpassword VNC_PASSWORD=vncpass VNC_GEOMETRY=1600x900 \
  ./scripts/run.sh --ubuntu 20.04 --variant desktop-ros --arch amd64 \
  --name ubuntu-dev-2004-desktop-ros-amd64-dev --ssh-port 2223 --web-port 6081 \
  --workspace "$PWD/workspace" --home-volume ubuntu-dev-2004-desktop-ros-amd64-home

ssh developer@localhost -p 2223
docker exec -it --user developer ubuntu-dev-2004-desktop-ros-amd64-dev bash
```

工作目录在容器内为 `/workspace`；用户卷挂载在 `/home/developer`，保存配置和 ROS 工作空间。Linux 绑定目录的权限沿用宿主机 UID/GID，不会递归修改宿主机文件；优先使用命名卷，或在宿主机调整工作目录权限。

需要局域网访问时，在上面的脚本命令加 `--bind 0.0.0.0`，连接宿主机实际局域网 IP。原生 Docker 将 `127.0.0.1:端口:端口` 改为 `0.0.0.0:端口:端口`。默认密码仅供本机开发，开放访问前请修改密码。

## 开发与自定义命令

进入容器后的基础检查和编译：

```bash
python --version
python3 --version
python3 -m pip --version
printf '#include <stdio.h>\nint main(void) { puts("hello"); return 0; }\n' > /tmp/hello.c
gcc -g /tmp/hello.c -o /tmp/hello && /tmp/hello
printf '#include <iostream>\nint main() { std::cout << "hello" << std::endl; }\n' > /tmp/hello.cpp
g++ -g /tmp/hello.cpp -o /tmp/hello-cpp && /tmp/hello-cpp
```

一次性命令会以默认普通用户执行；命令结束后容器退出，不会启动 SSH 或桌面：

```bash
docker run --rm --platform linux/amd64 ubuntu-dev:20.04-desktop-ros-amd64 python3 --version
docker run --rm -it --platform linux/amd64 ubuntu-dev:20.04-desktop-ros-amd64 bash
```

## ROS noetic 使用

入口命令、SSH 登录和交互式 Bash 自动加载 ROS。`docker exec` 的非交互命令应使用 `bash -lc`：

```bash
docker exec --user ubuntu ubuntu-dev-2004-desktop-ros-amd64 bash -lc 'echo "$ROS_DISTRO"; rospack find roscpp'
```

在容器内创建并编译工作空间：

```bash
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws/src
catkin_create_pkg hello_pkg roscpp rospy std_msgs
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

发布订阅演示、rosdep 初始化后首次更新、RViz 启动、跨容器网络配置见 [ROS 开发文档](../../docs/ros.md)。

## 日常管理与清理

```bash
docker logs --tail 100 ubuntu-dev-2004-desktop-ros-amd64
docker logs -f ubuntu-dev-2004-desktop-ros-amd64          # Ctrl+C 仅停止跟踪日志
docker stop ubuntu-dev-2004-desktop-ros-amd64
docker start ubuntu-dev-2004-desktop-ros-amd64            # 继续使用原容器及其数据
docker restart ubuntu-dev-2004-desktop-ros-amd64
docker stop ubuntu-dev-2004-desktop-ros-amd64
docker rm ubuntu-dev-2004-desktop-ros-amd64               # 删除容器可写层，保留绑定目录和命名卷
docker image rm ubuntu-dev:20.04-desktop-ros-amd64        # 其他容器仍引用镜像时需先处理这些容器
```

自定义示例的容器为 `ubuntu-dev-2004-desktop-ros-amd64-dev`，清理时请替换容器名。删除容器不删除工作目录或命名卷；确认不再需要持久化数据后，才手工执行 `docker volume rm ubuntu-dev-2004-desktop-ros-amd64-home`。

## 验证与排错

```bash
./scripts/smoke-test.sh --ubuntu 20.04 --variant desktop-ros --arch amd64
# 镜像已经构建时
./scripts/smoke-test.sh --ubuntu 20.04 --variant desktop-ros --arch amd64 --skip-build
```

同名容器使用 `docker start`，并行容器更换 `--name`、`--ssh-port`、`--web-port`。遇到 `exec format error` 检查平台和模拟支持；连接失败先查看日志与端口。桌面异常检查 /dev/shm、VNC 进程和浏览器控制台；22.04/20.04 的 Firefox 应为 Mozilla DEB。
旧 Ubuntu/ROS 的软件源和支持状态见 [排错文档](../../docs/troubleshooting.md)。实际验收情况见 [验证记录](../../docs/validation.md)，未通过的项目不能视为已验证。
