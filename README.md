# ros2_workspace
# 📱 ROS 2 Camera Stream from Android Phone

Stream live video from an Android phone straight into ROS 2 — no extra hardware, no USB camera, just your phone and Wi‑Fi (or a USB cable for less lag).

---

## 🧩 What This Package Does

Think of this node as a translator sitting between your phone and ROS 2:

```
[Android Phone]  --MJPEG over HTTP-->  [ROS 2 Node]  --sensor_msgs/Image-->  [/camera/image_raw]
   (IP Webcam app)                    (this package)                      (any ROS 2 subscriber)
```

In plain terms, the node:

1. **Connects** to your phone's camera feed using the free **IP Webcam** app.
2. **Reads** frames continuously in the background, so the video never stalls waiting on the network.
3. **Converts** each frame into a ROS 2 image message.
4. **Publishes** that message on the topic `/camera/image_raw`, ready for any other node to use — depth estimation, SLAM, object detection, you name it.

You don't need to understand ROS internals to use it — follow the steps below in order and you'll have a working camera topic in a few minutes.

---

## 📋 Table of Contents

1. [Before You Start](#1-before-you-start)
2. [Installation](#2-installation)
3. [Set Up the Phone](#3-set-up-the-phone)
4. [Run the Node](#4-run-the-node)
5. [Check That It's Working](#5-check-that-its-working)
6. [Common Problems & Fixes](#6-common-problems--fixes)
7. [Making It Faster / Smoother](#7-making-it-faster--smoother)
8. [Full Node Code](#8-full-node-code)
9. [What to Build Next](#9-what-to-build-next)
10. [License](#10-license)

---

## 1. Before You Start

Make sure you have:

| What | Details |
|---|---|
| 📱 Android phone | With [IP Webcam](https://play.google.com/store/apps/details?id=com.pass.webcam) installed (free, from Play Store) |
| 💻 Linux PC | Tested on Ubuntu 24.04 |
| 🤖 ROS 2 | Jazzy or later |
| 🌐 Network | Phone and PC on the **same Wi‑Fi**, or connected via **USB tethering** for lower latency |
| 🐍 Python | 3.12+ (use the system Python — not a virtual environment) |

Install the required system packages:

```bash
sudo apt install python3-opencv
sudo apt install ros-jazzy-cv-bridge ros-jazzy-image-transport ros-jazzy-image-view
```

---

## 2. Installation

**Step 1 — Create the package:**

```bash
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_python camera_stream \
    --dependencies rclpy cv_bridge sensor_msgs
```

**Step 2 — Add the node script.**
Copy the code from the [Full Node Code](#8-full-node-code) section into:

```
~/ros2_ws/src/camera_stream/camera_stream/camera_node.py
```

Then make it executable:

```bash
chmod +x ~/ros2_ws/src/camera_stream/camera_stream/camera_node.py
```

**Step 3 — Register the node as a runnable command.**
Open `setup.py` in the package root and add this inside `entry_points`:

```python
entry_points={
    'console_scripts': [
        'camera_node = camera_stream.camera_node:main',
    ],
},
```

**Step 4 — Build and source the workspace:**

```bash
cd ~/ros2_ws
colcon build --packages-select camera_stream --symlink-install
source install/setup.bash
```

> 💡 **Tip:** Run that `source` command in every new terminal, or add it to your `~/.bashrc` so it happens automatically.

---

## 3. Set Up the Phone

1. Open the **IP Webcam** app.
2. Scroll down and tap **Start Server**.
3. The app displays a URL, for example:

   ```
   http://192.168.1.12:8080/video
   ```

   Write this down — you'll need it in the next step. (It changes if your phone's IP address changes, e.g., after reconnecting to Wi‑Fi.)

---

## 4. Run the Node

The node has two adjustable settings:

| Parameter | Type | Default | What it controls |
|---|---|---|---|
| `stream_url` | string | `http://192.168.1.12:8080/video` | The address of your phone's video stream |
| `fps` | double | `30.0` | How many frames per second to publish |

**Run with defaults:**

```bash
ros2 run camera_stream camera_node
```

**Run with your own phone's URL and a custom frame rate:**

```bash
ros2 run camera_stream camera_node --ros-args \
    -p stream_url:=http://192.168.1.100:8080/video \
    -p fps:=15.0
```

If it connects successfully, you'll see:

```
[INFO] [camera_stream_node]: Camera node started. Streaming from: http://192.168.1.12:8080/video
[INFO] [camera_stream_node]: Published 100 frames
[INFO] [camera_stream_node]: Published 200 frames
```

---

## 5. Check That It's Working

**Confirm the topic is publishing at the expected rate:**

```bash
ros2 topic hz /camera/image_raw
```

**View the live video** (either works):

```bash
ros2 run image_view image_view image:=/camera/image_raw
```

```bash
ros2 run rqt_image_view rqt_image_view
```
Then pick `/camera/image_raw` from the dropdown menu.

---

## 6. Common Problems & Fixes

### ❌ GUI crashes with a `GLIBC_PRIVATE` or Qt Wayland error

**What you'll see:**
```
symbol lookup error: /snap/core20/current/lib/x86_64-linux-gnu/libpthread.so.0: undefined symbol: __libc_pthread_init
```

**Why it happens:** A Snap package (`core20`) ships its own broken `libpthread` library that shadows the correct system one.

**Fix:** Force the system library and X11 rendering:

```bash
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libpthread.so.0
export QT_QPA_PLATFORM=xcb
```

Add both lines to `~/.bashrc` so you don't have to retype them every session.

### ❌ `ModuleNotFoundError: No module named 'yaml'`

**Fix:**
```bash
sudo apt install python3-yaml
```

### ❌ Video is laggy or delayed

Try these, in order:

1. Lower the phone's resolution/frame rate inside the IP Webcam app (e.g., 640×480 @ 15 fps).
2. Set the node's `fps` parameter to match the phone's output rate.
3. Confirm you're running the version of the node below — it already includes the low-latency buffering fix (`CAP_PROP_BUFFERSIZE=1`).
4. Switch from Wi‑Fi to **USB tethering** for a stable, wired connection.

---

## 7. Making It Faster / Smoother

The node runs a **background thread** dedicated to reading frames from the phone, separate from the thread that publishes them to ROS 2. This matters because:

- Without it, a slow or jittery network connection would directly stall your ROS 2 publishing.
- With it, the reader thread always grabs the *newest* frame available, and the publisher just picks up whatever's freshest — so a brief network hiccup doesn't pile up delay.

Key techniques used:

| Technique | Why it helps |
|---|---|
| `cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)` | Stops OpenCV from queuing up old, stale frames |
| Dedicated reader thread | Keeps network I/O from blocking ROS 2's main loop |
| Timer just copies + publishes | Minimizes per-frame processing delay |

Still laggy? **USB tethering** almost always beats Wi‑Fi for this use case.

---

## 8. Full Node Code

Save as `~/ros2_ws/src/camera_stream/camera_stream/camera_node.py`:

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import sys
import threading
import time


class CameraStreamNode(Node):
    def __init__(self):
        super().__init__('camera_stream_node')

        # --- Parameters ---
        self.declare_parameter('stream_url', 'http://192.168.1.12:8080/video')
        self.declare_parameter('fps', 30.0)

        url = self.get_parameter('stream_url').get_parameter_value().string_value
        self.cap = cv2.VideoCapture(url)
        if not self.cap.isOpened():
            self.get_logger().error(f"Failed to open stream: {url}")
            sys.exit(1)

        # Keep only the latest frame in OpenCV's internal buffer
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # --- ROS 2 publisher ---
        self.bridge = CvBridge()
        self.publisher = self.create_publisher(
            Image,
            '/camera/image_raw',
            rclpy.qos.QoSProfile(
                depth=10,
                reliability=rclpy.qos.ReliabilityPolicy.BEST_EFFORT,
                durability=rclpy.qos.DurabilityPolicy.VOLATILE
            )
        )

        # --- Shared state between reader thread and publisher timer ---
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.frame_received = False

        # --- Background thread: continuously reads frames from the phone ---
        self.reader_thread = threading.Thread(target=self.reader_loop)
        self.reader_thread.daemon = True
        self.reader_thread.start()

        # --- Timer: publishes whatever the latest frame is, at a fixed rate ---
        fps = self.get_parameter('fps').get_parameter_value().double_value
        self.timer = self.create_timer(1.0 / fps, self.timer_callback)

        self.get_logger().info(f"Camera node started. Streaming from: {url}")
        self.frame_count = 0

    def reader_loop(self):
        """Runs continuously in the background, always fetching the newest frame."""
        while rclpy.ok():
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.latest_frame = frame
                    self.frame_received = True
            else:
                time.sleep(0.05)

    def timer_callback(self):
        """Runs at the configured FPS, publishing the latest available frame."""
        with self.frame_lock:
            if not self.frame_received:
                return
            frame = self.latest_frame.copy()
            self.frame_received = False

        self.frame_count += 1
        if self.frame_count % 100 == 0:
            self.get_logger().info(f"Published {self.frame_count} frames")

        try:
            ros_image = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            ros_image.header.stamp = self.get_clock().now().to_msg()
            ros_image.header.frame_id = "camera_frame"
            self.publisher.publish(ros_image)
        except Exception as e:
            self.get_logger().error(f"cv_bridge error: {e}")

    def destroy_node(self):
        self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraStreamNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
```

---

## 9. What to Build Next

Once `/camera/image_raw` is publishing reliably, you can plug it into:

- **Depth estimation** — e.g., run a MiDaS node on top of this stream.
- **Visual SLAM** — feed it into RTAB‑Map or ORB‑SLAM3.
- **IMU fusion** — combine with IMU data for more robust state estimation.
- **Recording** — save a rosbag for offline testing:

  ```bash
  ros2 bag record /camera/image_raw -o my_recording
  ```

---

## 10. License

Apache‑2.0 — open source, free to use and modify.

---

**Happy Robotics! 🤖**