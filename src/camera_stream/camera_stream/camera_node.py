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
        
        # Parameters
        self.declare_parameter('stream_url', 'http://192.168.1.12:8080/video')
        self.declare_parameter('fps', 30.0)
        
        url = self.get_parameter('stream_url').get_parameter_value().string_value
        
        # Open video stream with reduced buffer
        self.cap = cv2.VideoCapture(url)
        if not self.cap.isOpened():
            self.get_logger().error(f"Failed to open stream: {url}")
            sys.exit(1)
        
        # Set buffer size to 1 (low latency)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.bridge = CvBridge()
        
        # Publisher with Best-Effort QoS
        self.publisher = self.create_publisher(
            Image,
            '/camera/image_raw',
            rclpy.qos.QoSProfile(
                depth=10,
                reliability=rclpy.qos.ReliabilityPolicy.BEST_EFFORT,
                durability=rclpy.qos.DurabilityPolicy.VOLATILE
            )
        )
        
        # Shared frame storage (thread-safe)
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.frame_received = False
        
        # Start reader thread
        self.reader_thread = threading.Thread(target=self.reader_loop)
        self.reader_thread.daemon = True
        self.reader_thread.start()
        
        # Timer to publish at fixed rate
        fps = self.get_parameter('fps').get_parameter_value().double_value
        timer_period = 1.0 / fps
        self.timer = self.create_timer(timer_period, self.timer_callback)
        
        self.get_logger().info(f"Camera node started. Streaming from: {url}")
        self.frame_count = 0

    def reader_loop(self):
        """Continuously read frames from the stream and keep the latest one."""
        while rclpy.ok():
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.latest_frame = frame
                    self.frame_received = True
            else:
                self.get_logger().warn("Failed to grab frame, retrying...")
                time.sleep(0.05)  # avoid busy-wait

    def timer_callback(self):
        """Publish the latest frame at the desired FPS."""
        with self.frame_lock:
            if not self.frame_received:
                return
            frame = self.latest_frame.copy()  # copy to avoid race
            self.frame_received = False       # reset flag (optional)
        
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