"""minxg.screen.capture — multi-backend screen acquisition."""
from .adb_backend import adb_screencap, adb_uiautomator_dump, adb_device_connected
from .termux_backend import termux_api_screencap, termux_api_available
from .camera_backend import camera_photo, camera_photo_available
from .mock_backend import mock_screencap
from .screen_capture import ScreenCapture

__all__ = [
    "adb_screencap", "adb_uiautomator_dump", "adb_device_connected",
    "termux_api_screencap", "termux_api_available",
    "camera_photo", "camera_photo_available",
    "mock_screencap",
    "ScreenCapture",
]
