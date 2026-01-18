from __future__ import annotations

import sys
import threading
import tkinter as tk
import queue
from tkinter import messagebox
from typing import Callable, Optional

POSITION_EXIT_WARNING = "현재 보유중인 포지션이 있습니다. 프로그램을 종료하시기 전 포지션을 완전히 종료해주세요"


class ExitManager:
    def __init__(self, root: tk.Tk, app_name: str = "LeviaAutoTradeSystem") -> None:
        self.root = root
        self.app_name = app_name
        self._position_checker: Optional[Callable[[], bool]] = None
        self._closed = False
        self._tray: Optional[_TrayIcon] = None
        self._tray_queue: "queue.Queue[str]" = queue.Queue()
        self._tray_poll_job: Optional[str] = None

        try:
            self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        except tk.TclError:
            pass

        if sys.platform == "win32":
            self._tray = _TrayIcon(self.app_name, self._tray_queue)
            self._tray.start()
            self._start_tray_poll()

    def set_position_checker(self, checker: Optional[Callable[[], bool]]) -> None:
        self._position_checker = checker

    def hide_to_tray(self) -> None:
        if self._closed:
            return
        self._call_ui(self._withdraw_window)

    def show_window(self) -> None:
        if self._closed:
            return
        self._call_ui(self._restore_window)

    def request_exit(self) -> None:
        self._call_ui_deferred(self._handle_exit_request)

    def _handle_exit_request(self) -> None:
        if self._closed:
            return
        has_positions = False
        if self._position_checker is not None:
            try:
                has_positions = bool(self._position_checker())
            except Exception:
                has_positions = False
        if has_positions:
            self._restore_window()
            messagebox.showwarning("종료 안내", POSITION_EXIT_WARNING, parent=self.root)
            return
        self._shutdown()

    def _withdraw_window(self) -> None:
        try:
            self.root.withdraw()
        except tk.TclError:
            pass

    def _restore_window(self) -> None:
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    def _shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._tray_poll_job is not None:
            try:
                self.root.after_cancel(self._tray_poll_job)
            except tk.TclError:
                pass
            self._tray_poll_job = None
        if self._tray is not None:
            self._tray.stop()
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

    def _start_tray_poll(self) -> None:
        def poll() -> None:
            if self._closed:
                return
            try:
                while True:
                    action = self._tray_queue.get_nowait()
                    if action == "show":
                        self.show_window()
                    elif action == "exit":
                        self.request_exit()
            except queue.Empty:
                pass
            self._tray_poll_job = self.root.after(200, poll)

        self._tray_poll_job = self.root.after(200, poll)

    def _call_ui(self, func) -> None:
        try:
            if threading.current_thread() is threading.main_thread():
                func()
            else:
                self.root.after(0, func)
        except tk.TclError:
            pass

    def _call_ui_deferred(self, func) -> None:
        try:
            self.root.after(0, func)
        except tk.TclError:
            pass


if sys.platform == "win32":
    import ctypes
    import os
    import tempfile
    from pathlib import Path
    from ctypes import wintypes

    try:
        from PIL import Image
    except Exception:
        Image = None

    _PTR_SIZE = ctypes.sizeof(ctypes.c_void_p)
    _LONG_PTR = ctypes.c_longlong if _PTR_SIZE == 8 else ctypes.c_long
    LRESULT = getattr(wintypes, "LRESULT", _LONG_PTR)
    WPARAM = getattr(wintypes, "WPARAM", _LONG_PTR)
    LPARAM = getattr(wintypes, "LPARAM", _LONG_PTR)
    HANDLE = getattr(wintypes, "HANDLE", ctypes.c_void_p)
    HWND = getattr(wintypes, "HWND", HANDLE)
    HINSTANCE = getattr(wintypes, "HINSTANCE", HANDLE)
    HICON = getattr(wintypes, "HICON", HANDLE)
    HCURSOR = getattr(wintypes, "HCURSOR", HANDLE)
    HBRUSH = getattr(wintypes, "HBRUSH", HANDLE)
    LPCWSTR = getattr(wintypes, "LPCWSTR", ctypes.c_wchar_p)
    UINT = getattr(wintypes, "UINT", ctypes.c_uint)
    DWORD = getattr(wintypes, "DWORD", ctypes.c_uint32)
    WCHAR = getattr(wintypes, "WCHAR", ctypes.c_wchar)
    LONG = getattr(wintypes, "LONG", ctypes.c_long)
    BOOL = getattr(wintypes, "BOOL", ctypes.c_int)
    WORD = getattr(wintypes, "WORD", ctypes.c_ushort)
    BYTE = getattr(wintypes, "BYTE", ctypes.c_ubyte)

    WM_DESTROY = 0x0002
    WM_COMMAND = 0x0111
    WM_CLOSE = 0x0010
    WM_QUIT = 0x0012
    WM_APP = 0x8000
    WM_USER = 0x0400
    WM_TRAYICON = WM_USER + 20
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONUP = 0x0205
    WM_NULL = 0x0000

    NIM_ADD = 0x0000
    NIM_DELETE = 0x0002
    NIM_SETVERSION = 0x0004
    NIF_MESSAGE = 0x0001
    NIF_ICON = 0x0002
    NIF_TIP = 0x0004

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x00000010
    LR_DEFAULTSIZE = 0x00000040

    TPM_LEFTALIGN = 0x0000
    TPM_BOTTOMALIGN = 0x0020
    TPM_RIGHTBUTTON = 0x0002

    MF_STRING = 0x0000

    IDI_APPLICATION = 0x7F00

    MENU_SHOW = 1001
    MENU_EXIT = 1002

    NOTIFYICON_VERSION_4 = 4

    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", UINT),
            ("style", UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", HINSTANCE),
            ("hIcon", HICON),
            ("hCursor", HCURSOR),
            ("hbrBackground", HBRUSH),
            ("lpszMenuName", LPCWSTR),
            ("lpszClassName", LPCWSTR),
            ("hIconSm", HICON),
        ]

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", DWORD),
            ("Data2", WORD),
            ("Data3", WORD),
            ("Data4", BYTE * 8),
        ]

    class NOTIFYICONDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", DWORD),
            ("hWnd", HWND),
            ("uID", UINT),
            ("uFlags", UINT),
            ("uCallbackMessage", UINT),
            ("hIcon", HICON),
            ("szTip", WCHAR * 128),
            ("dwState", DWORD),
            ("dwStateMask", DWORD),
            ("szInfo", WCHAR * 256),
            ("uTimeoutOrVersion", UINT),
            ("szInfoTitle", WCHAR * 64),
            ("dwInfoFlags", DWORD),
            ("guidItem", GUID),
            ("hBalloonIcon", HICON),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [("x", LONG), ("y", LONG)]

    MSG = getattr(wintypes, "MSG", None)
    if MSG is None:
        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", HWND),
                ("message", UINT),
                ("wParam", WPARAM),
                ("lParam", LPARAM),
                ("time", DWORD),
                ("pt", POINT),
            ]

    class _TrayIcon:
        def __init__(self, tooltip: str, action_queue: "queue.Queue[str]") -> None:
            self._tooltip = tooltip
            self._queue = action_queue
            self._thread: Optional[threading.Thread] = None
            self._thread_id: Optional[int] = None
            self._hwnd: Optional[HWND] = None
            self._class_name = f"LTS_TRAY_{id(self)}"
            self._wndproc = None
            self._running = False
            self._stop_event = threading.Event()
            self._ready_event = threading.Event()
            self._icon_handle: Optional[HICON] = None
            self._icon_path: Optional[Path] = None

        def start(self) -> None:
            if self._thread is not None:
                return
            self._stop_event.clear()
            self._ready_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=False)
            self._thread.start()

        def stop(self) -> None:
            self._stop_event.set()
            self._running = False
            if self._hwnd is None and self._thread and self._thread.is_alive():
                self._ready_event.wait(timeout=0.5)
            if self._hwnd:
                ctypes.windll.user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            elif self._thread_id:
                try:
                    ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
                self._thread.join(timeout=3.0)
            self._thread = None

        def _run(self) -> None:
            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32
            kernel32 = ctypes.windll.kernel32
            hinst = kernel32.GetModuleHandleW(None)
            self._thread_id = kernel32.GetCurrentThreadId()
            if self._stop_event.is_set():
                self._ready_event.set()
                return
            self._running = True
            try:
                user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEX)]
                user32.RegisterClassExW.restype = ctypes.c_ushort
                user32.CreateWindowExW.argtypes = [
                    DWORD,
                    LPCWSTR,
                    LPCWSTR,
                    DWORD,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    HWND,
                    HANDLE,
                    HINSTANCE,
                    ctypes.c_void_p,
                ]
                user32.CreateWindowExW.restype = HWND
                user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
                user32.DefWindowProcW.restype = LRESULT
                user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
                user32.PostMessageW.restype = BOOL
                user32.PostThreadMessageW.argtypes = [DWORD, UINT, WPARAM, LPARAM]
                user32.PostThreadMessageW.restype = BOOL
                user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), HWND, UINT, UINT]
                user32.GetMessageW.restype = ctypes.c_int
                user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
                user32.TranslateMessage.restype = BOOL
                user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
                user32.DispatchMessageW.restype = LRESULT
                user32.LoadIconW.argtypes = [HINSTANCE, LPCWSTR]
                user32.LoadIconW.restype = HICON
                user32.LoadImageW.argtypes = [HINSTANCE, LPCWSTR, UINT, ctypes.c_int, ctypes.c_int, UINT]
                user32.LoadImageW.restype = HICON
                user32.DestroyIcon.argtypes = [HICON]
                user32.DestroyIcon.restype = BOOL
                user32.DestroyWindow.argtypes = [HWND]
                user32.DestroyWindow.restype = BOOL
                user32.CreatePopupMenu.argtypes = []
                user32.CreatePopupMenu.restype = HANDLE
                user32.AppendMenuW.argtypes = [HANDLE, UINT, UINT, LPCWSTR]
                user32.AppendMenuW.restype = BOOL
                user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
                user32.GetCursorPos.restype = BOOL
                user32.SetForegroundWindow.argtypes = [HWND]
                user32.SetForegroundWindow.restype = BOOL
                user32.TrackPopupMenu.argtypes = [HANDLE, UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, HWND, ctypes.c_void_p]
                user32.TrackPopupMenu.restype = BOOL
                user32.PostQuitMessage.argtypes = [ctypes.c_int]
                user32.PostQuitMessage.restype = None
                user32.DestroyMenu.argtypes = [HANDLE]
                user32.DestroyMenu.restype = BOOL
                shell32.Shell_NotifyIconW.argtypes = [DWORD, ctypes.POINTER(NOTIFYICONDATA)]
                shell32.Shell_NotifyIconW.restype = BOOL

                def _wnd_proc(hwnd, msg, wparam, lparam):
                    if not self._running:
                        if msg == WM_DESTROY:
                            self._remove_icon()
                            user32.PostQuitMessage(0)
                            return 0
                        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
                    if msg == WM_TRAYICON:
                        if self._stop_event.is_set():
                            return 0
                        event = int(lparam) & 0xFFFF
                        if event == WM_LBUTTONUP:
                            self._queue.put("show")
                        elif event == WM_RBUTTONUP:
                            self._show_menu(hwnd)
                        return 0
                    if msg == WM_CLOSE:
                        user32.DestroyWindow(hwnd)
                        return 0
                    if msg == WM_COMMAND:
                        if self._stop_event.is_set():
                            return 0
                        cmd_id = int(wparam) & 0xFFFF
                        if cmd_id == MENU_SHOW:
                            self._queue.put("show")
                        elif cmd_id == MENU_EXIT:
                            self._queue.put("exit")
                        return 0
                    if msg == WM_DESTROY:
                        self._remove_icon()
                        user32.PostQuitMessage(0)
                        return 0
                    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

                self._wndproc = WNDPROC(_wnd_proc)
                wndclass = WNDCLASSEX()
                wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
                wndclass.style = 0
                wndclass.lpfnWndProc = self._wndproc
                wndclass.cbClsExtra = 0
                wndclass.cbWndExtra = 0
                wndclass.hInstance = hinst
                wndclass.hIcon = None
                wndclass.hCursor = None
                wndclass.hbrBackground = None
                wndclass.lpszMenuName = None
                wndclass.lpszClassName = self._class_name
                wndclass.hIconSm = None
                user32.RegisterClassExW(ctypes.byref(wndclass))

                hwnd_message = HWND(-3)
                self._hwnd = user32.CreateWindowExW(
                    0,
                    self._class_name,
                    self._class_name,
                    0,
                    0,
                    0,
                    0,
                    0,
                    hwnd_message,
                    None,
                    hinst,
                    None,
                )
                self._ready_event.set()

                if not self._hwnd:
                    return
                if self._stop_event.is_set():
                    user32.DestroyWindow(self._hwnd)
                    return

                icon_handle = self._load_tray_icon()
                if not icon_handle:
                    icon_handle = user32.LoadIconW(None, ctypes.cast(ctypes.c_void_p(IDI_APPLICATION), LPCWSTR))
                self._add_icon(icon_handle)

                msg = MSG()
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            finally:
                self._running = False
                self._ready_event.set()

        def _load_tray_icon(self) -> Optional[HICON]:
            if Image is None:
                return None
            icon_path = Path(__file__).resolve().parent / "image" / "login_page" / "logo2.png"
            if not icon_path.exists():
                return None
            try:
                img = Image.open(icon_path).convert("RGBA")
            except Exception:
                return None
            try:
                width, height = img.size
                side = max(width, height)
                if width != height:
                    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
                    canvas.paste(img, ((side - width) // 2, (side - height) // 2))
                    img = canvas
                sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
                icon_file = Path(tempfile.gettempdir()) / f"lts_tray_{os.getpid()}.ico"
                img.save(icon_file, format="ICO", sizes=sizes)
                self._icon_path = icon_file
                hicon = ctypes.windll.user32.LoadImageW(
                    None,
                    str(icon_file),
                    IMAGE_ICON,
                    0,
                    0,
                    LR_LOADFROMFILE | LR_DEFAULTSIZE,
                )
                if not hicon:
                    return None
                self._icon_handle = hicon
                return hicon
            except Exception:
                return None

        def _add_icon(self, icon_handle) -> None:
            nid = NOTIFYICONDATA()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
            nid.hWnd = self._hwnd
            nid.uID = 1
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
            nid.uCallbackMessage = WM_TRAYICON
            nid.hIcon = icon_handle
            nid.szTip = self._tooltip
            nid.dwState = 0
            nid.dwStateMask = 0
            nid.szInfo = ""
            nid.uTimeoutOrVersion = NOTIFYICON_VERSION_4
            nid.szInfoTitle = ""
            nid.dwInfoFlags = 0
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(nid))

        def _remove_icon(self) -> None:
            if self._hwnd:
                nid = NOTIFYICONDATA()
                nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
                nid.hWnd = self._hwnd
                nid.uID = 1
                ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            if self._icon_handle:
                try:
                    ctypes.windll.user32.DestroyIcon(self._icon_handle)
                except Exception:
                    pass
                self._icon_handle = None
            if self._icon_path:
                try:
                    os.remove(self._icon_path)
                except Exception:
                    pass
                self._icon_path = None

        def _show_menu(self, hwnd) -> None:
            user32 = ctypes.windll.user32
            menu = user32.CreatePopupMenu()
            user32.AppendMenuW(menu, MF_STRING, MENU_SHOW, "열기")
            user32.AppendMenuW(menu, MF_STRING, MENU_EXIT, "종료")
            point = POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(hwnd)
            user32.TrackPopupMenu(
                menu,
                TPM_LEFTALIGN | TPM_BOTTOMALIGN | TPM_RIGHTBUTTON,
                point.x,
                point.y,
                0,
                hwnd,
                None,
            )
            user32.DestroyMenu(menu)
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)

else:

    class _TrayIcon:
        def __init__(self, tooltip: str, action_queue: "queue.Queue[str]") -> None:
            self._queue = action_queue

        def start(self) -> None:
            return

        def stop(self) -> None:
            return
