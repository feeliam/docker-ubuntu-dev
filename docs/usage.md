# 运行机制与配置

## 镜像与架构

每个架构目录使用官方对应版本 Ubuntu，包含全部构建文件，不要求先构建本仓库其他镜像。`--platform linux/amd64` 或 `linux/arm64` 决定基础镜像架构，Dockerfile 同时检查 `dpkg` 架构，防止误构建。跨架构需要原生节点或 QEMU，`docker buildx ls` 可以检查构建器能力。

ROS 的 `desktop` 软件包档位与 MATE 桌面不同：前者提供 RViz 等机器人应用，后者提供操作系统图形会话。

## 默认账号与环境变量

| 容器变量 | 默认值 | 用途 |
|---|---|---|
| `USER` | `ubuntu` | 合法的非 root Linux 用户名 |
| `PASSWORD` | `ubuntu` | SSH、sudo 密码，不支持换行 |
| `VNC_PASSWORD` | 同 `PASSWORD` | 桌面密码，不支持换行，仅前 8 字节有效 |
| `VNC_GEOMETRY` | `1920x1080` | 桌面分辨率，如 `1600x900` |
| `ROS_DISTRO` | 镜像固定 | melodic/noetic/humble，不应通过覆盖变量切换发行版 |

宿主机脚本使用 `CONTAINER_USER`、`CONTAINER_PASSWORD` 映射前两项，避免带入宿主机 `$USER`；`VNC_PASSWORD`、`VNC_GEOMETRY` 原样传递。环境密码可被具有 Docker 管理权限的人查看。

默认 sudo 要求用户密码。入口需要 root 初始化账号和服务，再使用普通用户运行桌面、自定义命令和 SSH 会话。启动镜像时不要传 `--user`；进入已经启动的容器则使用 `docker exec --user 用户名`。

## 启动机制

1. Tini 启动入口脚本，转发停止信号并回收子进程。
2. 创建或复用普通用户，加入 sudo 组，设置密码，并向空用户目录填充默认配置。不递归修改宿主机工作目录属主。
3. 建立 `/run/sshd`，使用 `ssh-keygen -A` 生成当前容器缺失的主机密钥。镜像不保留主机私钥，同一容器重启保留密钥。
4. ROS 变体加载 `/opt/ros/<发行版>/setup.bash`；系统登录和交互 Bash 也自动加载。
5. 默认 `services` 命令启动服务。传入其他命令时通过 gosu 降权执行，保留参数、信号和退出码。

普通版前台进程为 `sshd -D -e`。桌面版使用 Supervisor 管理系统 D-Bus、SSH、TigerVNC、websockify，TigerVNC `:1` 会话通过 `dbus-run-session` 启动 MATE。重启时清理这个显示号遗留的锁文件。

桌面链路：宿主机浏览器 → noVNC 页面 → websockify WebSocket → 容器内 `127.0.0.1:5901` TigerVNC → MATE。网页使用容器端口 `80`，默认映射为宿主机 `6080`。密码在浏览器连接时输入，不注入页面资源。容器内的 Firefox 用于桌面内浏览网页，与宿主机的 noVNC 浏览器不同。

## 原生命令

从仓库根目录执行：

```bash
docker buildx build --platform linux/arm64 --load \
  -t ubuntu-dev:22.04-desktop-ros-arm64 ./ubuntu2204-desktop-ros/arm64
docker run -d --platform linux/arm64 --name ubuntu-dev-demo \
  -p 127.0.0.1:2222:22 -p 127.0.0.1:6080:80 --shm-size=512m \
  -e USER=developer -e PASSWORD=devpassword \
  -e VNC_PASSWORD=vncpass -e VNC_GEOMETRY=1600x900 \
  --mount type=volume,source=ubuntu-dev-demo-home,target=/home/developer \
  ubuntu-dev:22.04-desktop-ros-arm64
ssh developer@localhost -p 2222
docker exec -it --user developer ubuntu-dev-demo bash
```

桌面地址：<http://localhost:6080/vnc.html?resize=remote>。断开 SSH 或关闭网页不会停止容器。

`docker exec` 不经过入口，非交互 ROS 命令使用 `docker exec --user developer ubuntu-dev-demo bash -lc 'ros2 pkg list'`。自定义用户名后，应同步修改 `docker exec --user` 和挂载的用户主目录。

## 持久化与公钥

脚本 `--workspace /路径` 将现有宿主机目录绑定到 `/workspace`；原生 Docker 对应 `--mount type=bind,source=/绝对路径,target=/workspace`。容器不递归修改目录属主，Linux 上需按宿主机 UID/GID 授予写权限，或使用命名卷。

`--home-volume 卷名` 保存 `/home/<用户名>` 的配置、工作空间和 rosdep 缓存。默认 UID/GID 由 Ubuntu `useradd` 分配，通常为 1000。复用主目录卷时保持用户名、UID/GID 一致；更改用户名请使用新的卷。删除容器不删除命名卷或绑定目录。

SSH 公钥可以在普通用户终端中配置，并用用户主目录卷保存：

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
printf '%s\n' '替换为你的完整 SSH 公钥' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

重建容器会生成新的 SSH 主机密钥，确认是自己的新容器后，用 `ssh-keygen -R '[localhost]:2222'` 清除旧记录。

## 局域网和多容器

脚本加 `--bind 0.0.0.0`，或原生 Docker 使用 `-p 0.0.0.0:6080:80 -p 0.0.0.0:2222:22`，其他设备连接宿主机局域网 IP；按防火墙规则开放端口并更改默认密码。默认网页为 HTTP，跨不可信网络可使用 SSH 隧道或自行配置 HTTPS 反向代理。

第二个容器使用独立名称和宿主机端口：

```bash
./scripts/run.sh --ubuntu 22.04 --variant desktop --arch arm64 \
  --name desktop-second --ssh-port 2223 --web-port 6081
```

`docker stop 名称` 停止，`docker start 名称` 继续原容器，`docker rm 名称` 删除已停止的容器。更改镜像、环境变量、端口或挂载应重建容器，`docker restart` 复用原参数。
