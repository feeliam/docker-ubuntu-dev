# ROS 开发

| Ubuntu | ROS | 工具与 Python |
|---|---|---|
| 18.04 | Melodic / ROS 1 | catkin、rosdep；`python` 为 2.7，另有 Python 3/pip3 |
| 20.04 | Noetic / ROS 1 | catkin、rosdep；Python 3 |
| 22.04 | Humble / ROS 2 | colcon、rosdep、vcstool；Python 3 |

`*-ros` 提供 `ros-base`，`*-desktop-ros` 提供 ROS `desktop`，包含 RViz。Melodic、Noetic 使用最终快照。

## 环境与依赖

SSH、交互 Bash、入口自定义命令自动加载 ROS。`docker exec` 非交互命令使用登录 Shell；将下面的“容器名”替换为对应 README 给出的实际名称：

```bash
docker exec --user ubuntu 容器名 bash -lc 'echo "$ROS_DISTRO"; env | grep ^ROS'
```

构建阶段已经执行 `rosdep init`。首次以当前普通用户使用 rosdep 时更新缓存，再在自己的工作空间根目录安装依赖：

```bash
rosdep update --include-eol-distros
rosdep install --from-paths src --ignore-src -r -y --rosdistro "$ROS_DISTRO"
```

缓存保存于主目录，不要再次以 root 执行 `rosdep init`。Melodic 的 `python`/`pip` 对应 Python 2.7，`python3`/`pip3` 对应 Python 3；不要随意升级覆盖系统 ROS 依赖。

## ROS 1：Melodic / Noetic

分别在三个容器终端执行以下三条命令：

```bash
# 终端 1
roscore
```

```bash
# 终端 2
rostopic pub -r 1 /hello std_msgs/String 'data: hello_ros'
```

```bash
# 终端 3
rostopic echo /hello
```

创建并编译包：

```bash
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws/src
catkin_create_pkg hello_pkg roscpp rospy std_msgs
cd ~/catkin_ws
catkin_make
source devel/setup.bash
rospack find hello_pkg
```

桌面 ROS 版在 MATE 终端执行 `rviz`。

## ROS 2：Humble

不需要 roscore。分别在两个容器终端执行：

```bash
# 终端 1
ros2 topic pub /hello std_msgs/msg/String 'data: hello_ros2' -r 1
```

```bash
# 终端 2
ros2 topic echo /hello std_msgs/msg/String
```

创建并编译包：

```bash
mkdir -p ~/ros_ws/src
cd ~/ros_ws/src
ros2 pkg create --build-type ament_cmake hello_pkg
cd ~/ros_ws
colcon build
source install/setup.bash
ros2 pkg prefix hello_pkg
```

桌面 ROS 版在 MATE 终端执行 `rviz2`。

## 跨容器通信

SSH/noVNC 端口映射不等于 ROS 网络配置。以上单容器示例无需额外参数。

ROS 1 节点必须能互相访问公布的主机地址及动态端口。先创建自定义网络 `docker network create ros-net`，原生 `docker run` 加 `--network ros-net --hostname ros-master --name ros-master`。主节点使用 `ROS_MASTER_URI=http://ros-master:11311`、`ROS_HOSTNAME=ros-master`；其他节点使用相同 `ROS_MASTER_URI` 和各自可达的容器主机名。例如 `docker exec --user ubuntu -e ROS_MASTER_URI=http://ros-master:11311 -e ROS_HOSTNAME=ros-master ros-master bash`。

ROS 2 节点应使用相同的 `ROS_DOMAIN_ID`，DDS 发现需要 UDP/组播可达。相同自定义 Docker 网络内通常可以通信，可在两边的 `docker run` 添加 `-e ROS_DOMAIN_ID=10`。原生 Linux 连接宿主机/局域网节点时可按实际网络使用 host 网络；Docker Desktop 的行为不同，需要配置 DDS 发现和可达地址，不能仅开放 SSH/网页端口。
