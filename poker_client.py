#!/usr/bin/env python3
"""
Poker Assistant Windows Client
Uses Windows RegisterHotKey API for reliable global hotkeys in games.
"""

import sys
import os
import time
import ctypes
from ctypes import wintypes
import tempfile
import logging
import pyautogui
import requests

# Windows constants
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
VK_G = ord('G')
VK_M = ord('M')

# Define WNDCLASSEX manually (not in ctypes.wintypes)
class WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("style", ctypes.c_uint),
        ("lpfnWndProc", ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_void_p),
        ("lpszClassName", ctypes.c_wchar_p),
        ("hIconSm", ctypes.c_void_p),
    ]

# Define MSG manually for message loop
class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_void_p),
        ("lParam", ctypes.c_void_p),
        ("time", ctypes.c_ulong),
        ("pt", ctypes.c_void_p),
    ]

SERVER_URL = "http://183.179.89.122:5199"
SCREENSHOT_DELAY = 0.3
TIMEOUT_SECONDS = 30

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(tempfile.gettempdir(), 'poker_client.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

running = True
last_screenshot_time = 0
MIN_HOTKEY_INTERVAL = 3

# Hotkey IDs
HOTKEY_ID_CASH = 1
HOTKEY_ID_MTT = 2

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def take_screenshot():
    try:
        pyautogui.FAILSAFE = False
        screenshot = pyautogui.screenshot()
        temp_path = os.path.join(tempfile.gettempdir(), f'poker_screenshot_{os.getpid()}.png')
        screenshot.save(temp_path)
        logger.info(f"Screenshot saved: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return None

def send_to_server(img_path, game_type):
    try:
        logger.info(f"Sending {game_type} screenshot to {SERVER_URL}...")
        with open(img_path, 'rb') as f:
            files = {'image': ('screenshot.png', f, 'image/png')}
            data = {'game_type': game_type}
            response = requests.post(
                f"{SERVER_URL}/analyze",
                files=files,
                data=data,
                timeout=TIMEOUT_SECONDS
            )
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Analysis received: {result.get('id')}")
            return result
        else:
            logger.error(f"Server error: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        logger.error("Server timeout - try again")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to server at {SERVER_URL}")
        return None
    except Exception as e:
        logger.error(f"Send error: {e}")
        return None
    finally:
        try:
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
        except:
            pass

def format_analysis_response(result):
    if not result:
        return "分析失败，请重试"
    analysis = result.get('analysis', {})
    advice = analysis.get('advice', '暂无建议')
    game_type = result.get('game_type', 'cash')
    icon = '🃏' if game_type == 'cash' else '🏆'
    return f"{icon} 【{game_type.upper()}】\n\n{advice}\n\nID: {result.get('id', 'N/A')}"

def handle_hotkey(game_type):
    global last_screenshot_time
    current_time = time.time()
    if current_time - last_screenshot_time < MIN_HOTKEY_INTERVAL:
        logger.info("Hotkey throttled")
        return
    last_screenshot_time = current_time
    mode = "CASH" if game_type == 'cash' else "MTT"
    logger.info(f"=== {mode} HOTKEY TRIGGERED ===")
    print(f"[{mode}] 正在截图...")
    time.sleep(SCREENSHOT_DELAY)
    img_path = take_screenshot()
    if not img_path:
        print("截图失败")
        return
    print(f"[{mode}] 正在发送分析...")
    result = send_to_server(img_path, game_type)
    print(format_analysis_response(result))

def register_hotkeys(user32, hwnd):
    """Register Ctrl+Shift+G and Ctrl+Shift+M as global hotkeys"""
    # Ctrl+Shift+G = Cash
    if not user32.RegisterHotKey(hwnd, HOTKEY_ID_CASH, MOD_CONTROL | MOD_SHIFT, VK_G):
        logger.error("Failed to register Ctrl+Shift+G")
        print("⚠️  无法注册 Ctrl+Shift+G (可能被其他程序占用)")
    else:
        print("✅ Ctrl+Shift+G 已注册 (Cash)")
    
    # Ctrl+Shift+M = MTT
    if not user32.RegisterHotKey(hwnd, HOTKEY_ID_MTT, MOD_CONTROL | MOD_SHIFT, VK_M):
        logger.error("Failed to register Ctrl+Shift+M")
        print("⚠️  无法注册 Ctrl+Shift+M (可能被其他程序占用)")
    else:
        print("✅ Ctrl+Shift+M 已注册 (MTT)")

def main():
    global running
    
    print("""
╔══════════════════════════════════════════════════════╗
║       POKER ASSISTANT - WINDOWS CLIENT              ║
╠══════════════════════════════════════════════════════╣
║  Ctrl+Shift+G  ->  Cash Game 分析                  ║
║  Ctrl+Shift+M  ->  MTT Tournament 分析             ║
║                                                      ║
║  Server:  """)
    print(f"  {SERVER_URL}")
    print("""║  按 Ctrl+C 退出                                       ║
╚══════════════════════════════════════════════════════╝
    """)
    
    if not is_admin():
        print("⚠️  建议以管理员身份运行以确保热键正常工作")
    
    # Check server connectivity
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Server connected: {SERVER_URL}")
        else:
            print(f"⚠️  Server returned: {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print(f"   请确保 server 正在运行")
        sys.exit(1)
    
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.1
    
    # Windows message loop for hotkeys
    user32 = ctypes.windll.user32
    WM_QUIT = 0x0012
    
    # Create a message-only window for hotkey messages
    wc = WNDCLASSEX()
    wc.cbSize = ctypes.sizeof(WNDCLASSEX)
    # Window procedure - use ctypes raw types, not wintypes (which are already WinFunctionType)
    WNDPROC = ctypes.WINFUNCTYPE(
        ctypes.c_long,        # LRESULT (return type)
        ctypes.c_void_p,      # HWND
        ctypes.c_uint,        # UINT
        ctypes.c_void_p,      # WPARAM
        ctypes.c_void_p       # LPARAM
    )
    wc.lpfnWndProc = WNDPROC(lambda h, m, w, l: 0)
    wc.hInstance = user32.GetModuleHandleW(None)
    wc.lpszClassName = "PokerHotkeyClass"
    
    class_atom = user32.RegisterClassExW(ctypes.byref(wc))
    if not class_atom:
        print("❌ 无法注册窗口类")
        sys.exit(1)
    
    hwnd = user32.CreateWindowExW(
        0, class_atom, "Poker Assistant",
        0, 0, 0, 0, 0,
        None, None, wc.hInstance, None
    )
    
    if not hwnd:
        print("❌ 无法创建窗口")
        sys.exit(1)
    
    # Register hotkeys
    register_hotkeys(user32, hwnd)
    
    print("\n等待热键按下... (切换到 GG Poker 窗口，按下 Ctrl+Shift+G 或 Ctrl+Shift+M)\n")
    
    # Message loop
    msg = MSG()
    while running:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0 or ret == -1:
            break
        
        if msg.message == WM_HOTKEY:
            if msg.wParam == HOTKEY_ID_CASH:
                handle_hotkey('cash')
            elif msg.wParam == HOTKEY_ID_MTT:
                handle_hotkey('mtt')
        else:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    
    # Cleanup
    user32.UnregisterHotKey(hwnd, HOTKEY_ID_CASH)
    user32.UnregisterHotKey(hwnd, HOTKEY_ID_MTT)
    user32.DestroyWindow(hwnd)
    print("\n退出。")

if __name__ == '__main__':
    main()
