"""Capture the fixture display on a dedicated GDK process/main thread."""
import sys
import gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk
root = Gdk.get_default_root_window()
pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
_, data = pixbuf.save_to_bufferv("png", [], [])
sys.stdout.buffer.write(bytes(data))
