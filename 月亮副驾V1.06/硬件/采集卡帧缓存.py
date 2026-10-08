# -*- coding: utf-8 -*-
import threading
import time


class FrameBuffer:
    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = FrameBuffer()
        return cls._instance

    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._timestamp = 0.0

    def set_frame(self, frame):
        with self._lock:
            self._frame = frame
            self._timestamp = time.time()

    def get_frame(self, copy=False):
        with self._lock:
            if self._frame is None:
                return None, -1
            return self._frame, time.time() - self._timestamp

    def clear(self):
        with self._lock:
            self._frame = None
            self._timestamp = 0.0