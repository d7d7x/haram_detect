import os
import sys
import json
import time
import queue
import logging
import threading
import ctypes
from typing import Any, Optional, Dict, List

logger = logging.getLogger(__name__)

# Win32 Constants for Named Pipe access
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = -1

class MPVIPCController:
    """
    Windows-native MPV JSON IPC Controller.
    Manages named pipe connection to an MPV process for real-time playback control,
    property querying, audio muting, and subtitle injection.
    """

    def __init__(self, pipe_name: str = "autocensor_mpv_ipc"):
        self.pipe_name = pipe_name
        self.full_pipe_path = f"\\\\.\\pipe\\{pipe_name}" if not pipe_name.startswith("\\\\.\\pipe\\") else pipe_name
        self._handle = None
        self._connected = False
        self._lock = threading.Lock()
        self._request_id = 0
        self._pending_responses: Dict[int, queue.Queue] = {}
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False

        # Cached states
        self._cached_time_pos: Optional[float] = None
        self._cached_pause: bool = False
        self._cached_mute: bool = False

    def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to MPV Windows named pipe with retry timeout.
        """
        start_time = time.time()
        logger.info(f"Connecting to MPV IPC pipe: {self.full_pipe_path}...")

        while time.time() - start_time < timeout:
            try:
                if sys.platform == "win32":
                    handle = ctypes.windll.kernel32.CreateFileW(
                        self.full_pipe_path,
                        GENERIC_READ | GENERIC_WRITE,
                        0,
                        None,
                        OPEN_EXISTING,
                        FILE_ATTRIBUTE_NORMAL,
                        None
                    )
                    if handle != INVALID_HANDLE_VALUE:
                        self._handle = handle
                        self._connected = True
                        self._running = True
                        logger.info(f"Connected to MPV IPC named pipe: {self.pipe_name}")

                        # Start background listener thread
                        self._listener_thread = threading.Thread(target=self._read_loop, daemon=True)
                        self._listener_thread.start()

                        # Enable time-pos and pause property observations if desired
                        self.observe_property("time-pos")
                        self.observe_property("pause")
                        return True
                else:
                    # Unix domain socket fallback for non-Windows (if needed)
                    import socket
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect(self.pipe_name)
                    self._handle = sock
                    self._connected = True
                    self._running = True
                    self._listener_thread = threading.Thread(target=self._read_loop_socket, daemon=True)
                    self._listener_thread.start()
                    return True

            except Exception as e:
                logger.debug(f"Waiting for MPV pipe... ({e})")
            
            time.sleep(0.15)

        logger.error(f"Failed to connect to MPV IPC pipe within {timeout}s")
        return False

    def is_connected(self) -> bool:
        return self._connected and self._running

    def _next_request_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id

    def _write_raw(self, payload_bytes: bytes) -> bool:
        if not self._connected or not self._handle:
            return False

        try:
            if sys.platform == "win32":
                written = ctypes.c_ulong(0)
                res = ctypes.windll.kernel32.WriteFile(
                    self._handle,
                    payload_bytes,
                    len(payload_bytes),
                    ctypes.byref(written),
                    None
                )
                return bool(res)
            else:
                self._handle.sendall(payload_bytes)
                return True
        except Exception as e:
            logger.error(f"Failed to write to MPV IPC pipe: {e}")
            self._connected = False
            return False

    def send_command(self, cmd_name: str, *args, timeout: float = 2.0) -> Optional[Any]:
        """
        Send a JSON IPC command to MPV and return response data.
        Example: send_command("set_property", "mute", True)
        """
        if not self._connected:
            return None

        req_id = self._next_request_id()
        cmd_list = [cmd_name] + list(args)
        payload = {
            "command": cmd_list,
            "request_id": req_id
        }

        resp_queue = queue.Queue()
        with self._lock:
            self._pending_responses[req_id] = resp_queue

        raw_str = json.dumps(payload) + "\n"
        if not self._write_raw(raw_str.encode("utf-8")):
            with self._lock:
                self._pending_responses.pop(req_id, None)
            return None

        try:
            resp = resp_queue.get(timeout=timeout)
            if isinstance(resp, dict):
                if resp.get("error") == "success":
                    return resp.get("data", True)
                else:
                    logger.debug(f"MPV IPC command '{cmd_name}' error response: {resp.get('error')}")
                    return None
            return resp
        except queue.Empty:
            logger.debug(f"MPV IPC command '{cmd_name}' timed out (request_id={req_id})")
            return None
        finally:
            with self._lock:
                self._pending_responses.pop(req_id, None)

    def observe_property(self, prop_name: str, obs_id: int = 1):
        """Observe property changes from MPV."""
        self.send_command("observe_property", obs_id, prop_name)

    def get_property(self, prop_name: str) -> Optional[Any]:
        """Query MPV property value."""
        return self.send_command("get_property", prop_name)

    def set_property(self, prop_name: str, value: Any) -> bool:
        """Set MPV property value."""
        res = self.send_command("set_property", prop_name, value)
        return res is not None

    def get_time_pos(self) -> Optional[float]:
        """Get current playback position in seconds."""
        val = self.get_property("time-pos")
        if val is not None:
            try:
                self._cached_time_pos = float(val)
                return self._cached_time_pos
            except (ValueError, TypeError):
                pass
        return self._cached_time_pos

    def is_paused(self) -> bool:
        """Get pause state of MPV."""
        val = self.get_property("pause")
        if isinstance(val, bool):
            self._cached_pause = val
            return val
        return self._cached_pause

    def set_pause(self, state: bool) -> bool:
        """Pause or resume playback."""
        self._cached_pause = state
        return self.set_property("pause", state)

    def mute(self, state: bool = True) -> bool:
        """Mute or unmute MPV audio track."""
        if self._cached_mute == state:
            return True
        res = self.set_property("mute", state)
        if res:
            self._cached_mute = state
        return res

    def unmute(self) -> bool:
        """Unmute MPV audio track."""
        return self.mute(False)

    def load_subtitle(self, sub_path: str, flags: str = "select") -> bool:
        """Inject cleaned subtitle file into MPV playback."""
        abs_path = os.path.abspath(sub_path)
        logger.info(f"Injecting subtitle into MPV via IPC: {abs_path}")
        res = self.send_command("sub-add", abs_path, flags)
        return res is not None

    def seek(self, seconds: float, mode: str = "absolute") -> bool:
        """Seek MPV playback to timestamp."""
        res = self.send_command("seek", seconds, mode)
        return res is not None

    def _read_loop(self):
        """Background thread reading lines from Windows Win32 Named Pipe."""
        buffer = ""
        read_buf = ctypes.create_string_buffer(4096)
        bytes_read = ctypes.c_ulong(0)

        while self._running and self._handle:
            try:
                res = ctypes.windll.kernel32.ReadFile(
                    self._handle,
                    read_buf,
                    ctypes.sizeof(read_buf) - 1,
                    ctypes.byref(bytes_read),
                    None
                )
                if not res or bytes_read.value == 0:
                    time.sleep(0.01)
                    continue

                chunk = read_buf.raw[:bytes_read.value].decode("utf-8", errors="replace")
                buffer += chunk

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._handle_json_message(line)

            except Exception as e:
                logger.debug(f"IPC read loop error or closed pipe: {e}")
                break

        self._connected = False
        self._running = False

    def _read_loop_socket(self):
        """Fallback read loop for UNIX domain sockets."""
        buffer = ""
        while self._running and self._handle:
            try:
                chunk = self._handle.recv(4096).decode("utf-8", errors="replace")
                if not chunk:
                    break
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._handle_json_message(line)
            except Exception:
                break
        self._connected = False
        self._running = False

    def _handle_json_message(self, raw_json: str):
        """Process incoming JSON message from MPV."""
        try:
            msg = json.loads(raw_json)
        except Exception:
            return

        # Check if response to a request_id
        if "request_id" in msg:
            req_id = msg["request_id"]
            with self._lock:
                q = self._pending_responses.get(req_id)
            if q:
                q.put(msg)
            return

        # Check if property change event
        if msg.get("event") == "property-change":
            name = msg.get("name")
            data = msg.get("data")
            if name == "time-pos" and data is not None:
                try:
                    self._cached_time_pos = float(data)
                except (ValueError, TypeError):
                    pass
            elif name == "pause" and data is not None:
                self._cached_pause = bool(data)
            elif name == "mute" and data is not None:
                self._cached_mute = bool(data)

    def close(self):
        """Cleanly close MPV IPC controller and named pipe handle."""
        self._running = False
        self._connected = False
        if sys.platform == "win32" and self._handle and self._handle != INVALID_HANDLE_VALUE:
            try:
                ctypes.windll.kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None
        elif self._handle:
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None
        logger.info("MPV IPC Controller closed.")
