# armando_description — Classwork 1
 
**Robotics Lab 2026 — Prof. Mario Selvaggio**
Author: Paolo Iaccarino
 
This package is the [RoboticsLab2026/armando_description](https://github.com/RoboticsLab2026/armando_description) package, extended with:
 
1. a **second camera mounted on the wrist** (end effector) of the manipulator, pointing along the approach direction and visible from ROS 2;
2. a **keyboard teleoperation node** (`armando_teleop.py`) that moves the arm joints `j0`–`j3`.
The package runs inside the Docker environment from Classwork 0: [iaccapaolo/iaccarino_rl26](https://github.com/iaccapaolo/iaccarino_rl26).
 
---
 
## Contents
 
- [1. From a clean machine to a running simulation](#1-from-a-clean-machine-to-a-running-simulation)
- [2. Verify the controllers](#2-verify-the-controllers)
- [3. Verify the wrist camera](#3-verify-the-wrist-camera)
- [4. Run the teleoperation node](#4-run-the-teleoperation-node)
- [5. Files created and modified](#5-files-created-and-modified)
- [6. Notes](#6-notes)
---
 
## 1. From a clean machine to a running simulation
 
**Requirements on the host:** Ubuntu with Docker and Git installed.
 
### 1.1 Clone the workspace and this package
 
```bash
cd ~
git clone https://github.com/iaccapaolo/iaccarino_rl26.git
cd iaccarino_rl26/src
git clone https://github.com/iaccapaolo/armando_description.git
```
 
`iaccarino_rl26/src` is mounted inside the container as `/home/user/ros2_ws/src`, so the package is visible from both sides.
 
### 1.2 Build the Docker image
 
If an image with the same name already exists, remove it first:
 
```bash
docker images                 # find the IMAGE ID
docker rmi <IMAGE_ID>
```
 
Build the image (the script must be launched from the `docker_scripts` folder, where the Dockerfile is):
 
```bash
cd ~/iaccarino_rl26/docker_scripts
./docker_build_image.sh armando_img
```
 
### 1.3 Start the container
 
```bash
cd ~/iaccarino_rl26
./docker_scripts/docker_run_container.sh armando_img armando_cont iaccarino_rl26/src
```
 
The third argument is the folder to mount, relative to the home directory.
 
To open **additional terminals** inside the running container (from the host):
 
```bash
cd ~/iaccarino_rl26
./docker_scripts/docker_connect.sh armando_cont
```
 
### 1.4 Install the dependencies with rosdep
 
Inside the container (the password for `sudo` is `user`):
 
```bash
cd /home/user/ros2_ws
sudo apt update
rosdep update
rosdep install --from-paths src --ignore-src -y
```
 
`rosdep` reads the `package.xml` files in `src/`, maps every ROS dependency (e.g. `ros_gz_sim`, `gz_ros2_control`, `aruco_ros`, `rclpy`) to the corresponding Ubuntu package and installs it with `apt`.
 
> The container is started with `--rm`: everything installed here is lost when the container is closed, so this step must be repeated at every new container.
 
### 1.5 Build the workspace and launch the simulation
 
```bash
cd /home/user/ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch armando_description armando_gazebo.launch.py
```
 
Gazebo opens with Armando on the workbench.
 
> In every new terminal opened inside the container, run `cd /home/user/ros2_ws && source install/setup.bash` before using any `ros2` command on this package.
 
---
 
## 2. Verify the controllers
 
In a second terminal:
 
```bash
ros2 control list_controllers
```
 
Expected output: `joint_state_broadcaster` and `joint_trajectory_controller` both **active**.
 
Send the arm to a configuration from the terminal:
 
```bash
ros2 topic pub --once /joint_trajectory_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory "{
    joint_names: ['j0', 'j1', 'j2', 'j3'],
    points: [
      {
        positions: [0.5, -0.3, 0.8, 0.0],
        time_from_start: { sec: 2, nanosec: 0 }
      }
    ]
  }"
```
 
The arm must reach the configuration in Gazebo.
 
---
 
## 3. Verify the wrist camera
 
With the simulation running:
 
```bash
# Topics on the Gazebo side
ign topic -l | grep -i camera        # or: gz topic -l
 
# Topics on the ROS 2 side (through the bridge)
ros2 topic list | grep camera
ros2 topic hz /wrist_camera/image_raw     # ~30 Hz
 
# Image viewer
ros2 run rqt_image_view rqt_image_view
```
 
In `rqt_image_view` select `/wrist_camera/image_raw`. Moving the arm (with `ros2 topic pub` or with the teleop node) the image moves with it.
 
Expected camera topics in ROS 2:
 
| Camera | Image | Calibration | Mounted on |
|---|---|---|---|
| Fixed (original) | `/camera/image_raw` | `/camera/camera_info` | `base_link` (via `camera_mount`), fixed |
| Wrist (new) | `/wrist_camera/image_raw` | `/wrist_camera/camera_info` | `crawer_base`, moves with the arm |
 
To inspect the frames in RViz:
 
```bash
rviz2 --ros-args -p use_sim_time:=true
```
 
Set **Fixed Frame** to `world`, add **RobotModel** (topic `/robot_description`) and **TF**. The x axis (red) of `wrist_camera_link` is aligned with the z axis (blue) of `crawer_base`, i.e. the approach direction of the gripper.
 
---
 
## 4. Run the teleoperation node
 
With the simulation running, in a **dedicated terminal** inside the container (the node reads the keyboard, so it cannot be started from a launch file):
 
```bash
cd /home/user/ros2_ws
source install/setup.bash
ros2 run armando_description armando_teleop.py
```
 
| Key | Action |
|---|---|
| `q` / `a` | `j0` + / − |
| `w` / `s` | `j1` + / − |
| `e` / `d` | `j2` + / − |
| `r` / `f` | `j3` + / − |
| `h` | home (all joints to 0) |
| `x` or `Ctrl+C` | quit |
 
Each key press moves the joint by 0.05 rad in 0.2 s (0.25 rad/s). Positions are clipped to the joint limits of the URDF (±3.14 rad).
 
**Full test of the assignment:** keep Gazebo, `rqt_image_view` on `/wrist_camera/image_raw` and the teleop node open at the same time; pressing the keys, the arm moves and the wrist camera image moves with it.
 
### How the node works
 
1. Subscribes to `/joint_states` and stores the current position of `j0`–`j3` **once**, matching joints by name. This way the arm does not jump to zero at the first key press.
2. Puts the terminal in *cbreak* mode (one key at a time, no Enter, no echo) and reads keys with `select()` and a timeout, so the loop never blocks and ROS keeps spinning.
3. At every key press updates the target of one joint and publishes a `trajectory_msgs/JointTrajectory` with a single point on `/joint_trajectory_controller/joint_trajectory` — the same message sent by hand in section 2.
4. On exit restores the terminal settings and shuts the node down.
---
 
## 5. Files created and modified
 
```
armando_description/
├── CMakeLists.txt                       ← modified
├── package.xml                          ← modified
├── README.md                            ← new
├── launch/
│   └── armando_gazebo.launch.py         ← modified
├── scripts/
│   └── armando_teleop.py                ← new
└── urdf/
    ├── arm.urdf.xacro                   ← modified
    ├── armando_body.urdf.xacro          (unchanged)
    ├── armando_camera.urdf.xacro        (unchanged)
    └── armando_wrist_camera.urdf.xacro  ← new
```
 
### `urdf/armando_wrist_camera.urdf.xacro` (new)
 
Second camera, built from the same structure as `armando_camera.urdf.xacro`:
 
| Element | Value | Why |
|---|---|---|
| `wrist_camera_joint` (fixed) | parent `crawer_base` → child `wrist_camera_link` | Hangs off the kinematic chain (gripper base), so the camera moves with the arm. The original camera hangs off `base_link` and is fixed. |
| `origin xyz` | `0 0.05 0` | 5 cm on the +y side of the gripper, so the camera body does not overlap the gripper. |
| `origin rpy` | `0 -1.5708 0` | The Gazebo camera looks along +x of its link. A −90° pitch brings that axis onto +z of `crawer_base`, the approach direction of the gripper. |
| `wrist_camera_link` | red box 1×3×3 cm | Visual only (fixed joint: no inertia needed). |
| `wrist_camera_optical_joint` / `wrist_camera_optical_frame` | `rpy="-π/2 0 -π/2"` | Converts from the link convention (x forward) to the optical convention used by images (z forward, x right, y down). |
| `<sensor name="wrist_camera">` | `<topic>wrist_camera/image_raw</topic>` | Unique topic. The namespace also makes Gazebo publish the calibration on `wrist_camera/camera_info` instead of `/camera_info`, which is already used by the fixed camera. |
| `<gz_frame_id>` | `wrist_camera_optical_frame` | Frame written in the header of the image messages. |
| Resolution | 640×480 | Lighter than 1920×1080 with two cameras rendering at 30 Hz. |
| `<near>` | 0.02 m | With 0.1 m, objects close to the gripper would be clipped exactly when approaching them. |
 
All names (joints, links, sensor, topic, frame) have the `wrist_` prefix: with two cameras in the same robot, duplicate names would make the model fail to load or the topics collide.
 
### `urdf/arm.urdf.xacro` (modified)
 
Added the include of the new camera, next to the original one:
 
```xml
<xacro:include filename="armando_camera.urdf.xacro"/>
<xacro:include filename="armando_wrist_camera.urdf.xacro"/>
```
 
### `launch/armando_gazebo.launch.py` (modified)
 
Added two entries to the `arguments` of `bridge_node` (`ros_gz_bridge/parameter_bridge`), otherwise the images stay inside Gazebo:
 
```python
'/wrist_camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image',
'/wrist_camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
```
 
Syntax: `topic@ROS_type<dir>Gazebo_type`, where `[` means Gazebo → ROS (a sensor only produces data). No remapping is needed because the topic name is already the ROS one.
 
### `scripts/armando_teleop.py` (new)
 
Keyboard teleoperation node, described in [section 4](#4-run-the-teleoperation-node). The file starts with `#!/usr/bin/env python3` and is executable (`chmod +x`).
 
### `CMakeLists.txt` (modified)
 
Installs the node where `ros2 run` looks for executables (`install/armando_description/lib/armando_description/`):
 
```cmake
install(PROGRAMS scripts/armando_teleop.py
  DESTINATION lib/${PROJECT_NAME})
```
 
`PROGRAMS` (instead of `FILES`) keeps the execute permission.
 
### `package.xml` (modified)
 
Added the runtime dependencies of the node, so that `rosdep install` installs them on a clean machine:
 
```xml
<exec_depend>rclpy</exec_depend>
<exec_depend>sensor_msgs</exec_depend>
<exec_depend>trajectory_msgs</exec_depend>
<exec_depend>builtin_interfaces</exec_depend>
```
 
---
 
## 6. Notes
 
- **Dependencies are not persistent.** They are installed in the container, not in the image, and the container is removed on exit (`--rm`). As required by the assignment, the generic Dockerfile is not modified: `rosdep install` must be run at every new container (section 1.4).
- **After adding new files** (e.g. a new xacro or script) run `colcon build` again: `--symlink-install` updates modified files automatically, but new files must be installed.
- **Publishing.** This repository contains only the `armando_description` package; it was created by replacing the original remote:
```bash
  cd /home/user/ros2_ws/src/armando_description
  git remote remove origin
  git remote add origin https://github.com/iaccapaolo/armando_description.git
  git add .
  git commit -m "Add wrist camera and teleoperation node"
  git branch -M main
  git push -u origin main
```
