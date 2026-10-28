# 排错与兼容性

## 构建与软件源

- `exec format error`：检查目录架构、`--platform`、宿主机架构、QEMU/native builder。`docker buildx ls` 查看平台；不支持模拟时换对应架构机器构建，不要去掉 Dockerfile 的架构检查。
- Docker 连接失败：启动 Docker Engine/Desktop，检查 `docker context ls` 和 socket 访问权限。
- APT 下载失败：检查网络、Docker 代理、DNS；重试会复用已成功的层。不要关闭签名校验绕过问题。
- 18.04、20.04 已结束标准维护，不自动启用 Ubuntu Pro/ESM。结束标准维护不代表应盲目把源改成 old-releases；先核实该版本和架构实际源的位置。
- Melodic、Noetic 使用官方最终快照和独立签名 keyring。Humble 使用固定版本官方 `ros2-apt-source` 包和 SHA-256 校验。网络、证书或上游仓库不可用时需保留原始错误。
- 普通镜像使用系统 Python 3，Melodic 镜像的 `python` 为 2.7 并保留 Python 3；不同 Ubuntu 的 Python 3 小版本不同。
- 18.04 仓库未提供 Tini，本项目从上游获取固定版本的对应架构静态二进制，并校验固定 SHA-256；其他版本使用 Ubuntu 的 Tini 包。

## 端口与账号

先执行 `docker ps -a`、`docker logs --tail 100 容器名`。同名容器用 `docker start` 或换 `--name`；端口占用改 `--ssh-port`、`--web-port`。脚本检查本机 IPv4 端口，适用于本地 Docker Engine/Desktop；远程 Docker context 应在远端检查端口并使用原生 Docker 命令。

环境变量在创建容器时传入，重启不会修改。自定义用户后同步更改 SSH 用户名、`docker exec --user` 和主目录挂载路径；不要用 `--user` 启动入口。sudo 要求用户密码。

重建容器会生成新的 SSH 主机密钥。确认是自己的新容器后运行 `ssh-keygen -R '[localhost]:2222'`。公钥登录失败检查 `.ssh` 权限为 700、`authorized_keys` 为 600，且属于目标用户。

## 网页桌面

1. 默认地址 `http://localhost:6080/vnc.html?resize=remote`；检查容器 `80` 端口映射，连接时输入 VNC 密码。
2. 查看容器日志及服务状态：`docker exec 容器名 supervisorctl -c /run/ubuntu-dev-supervisor.conf status`。
3. VNC 密码默认继承用户密码，仅前 8 字节有效；建议单独设置 6–8 个 ASCII 字符。
4. 图形程序异常检查共享内存，启动时使用 `--shm-size=512m`；也可使用新主目录卷排除旧配置影响。
5. 镜像无需 systemd 或显示器，入口自动启动独立 D-Bus/MATE 会话；不要再手工启动第二个 `:1` VNC 服务。

Firefox 在 18.04 使用旧发行版兼容 DEB，版本受该仓库限制；20.04/22.04 使用 Mozilla 官方 DEB，不依赖 Snap。以普通用户运行浏览器。通过 `docker exec` 启动图形程序时指定显示号和主目录：

```bash
docker exec --user ubuntu -e HOME=/home/ubuntu -e DISPLAY=:1 容器名 firefox about:blank
```

RViz 在虚拟显示中使用软件渲染，性能取决于分辨率和宿主机资源。先核查 `DISPLAY=:1`、ROS 环境和 VNC 日志；默认不配置 GPU 直通。

## 上游资料

- [参考桌面实现](https://github.com/Tiryoh/docker-ros2-desktop-vnc)
- [官方 ROS Dockerfiles](https://github.com/osrf/docker_images)
- [ROS 1 平台要求](https://github.com/ros-infrastructure/rep/blob/master/rep-0003.rst)
- [ROS 2 平台要求](https://github.com/ros-infrastructure/rep/blob/master/rep-2000.rst)
- [Mozilla 安装说明](https://support.mozilla.org/en-US/kb/install-firefox-linux)
- [Ubuntu 发行周期](https://ubuntu.com/about/release-cycle)
