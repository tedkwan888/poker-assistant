#!/usr/bin/env python3
"""
Poker Assistant Windows Client
Uses GetAsyncKeyState polling for reliable global hotkeys in fullscreen games.
"""

import sys
import os
import time
import ctypes
import tempfile
import logging
import threading
import pyautogui
import requests

# Windows constants
VK_G = ord('G')
VK_M = ord('M')
VK_CONTROL = 0x11
VK_SHIFT = 0x10

SERVER_URL = "http://183.179.89.122:5199"
SCREENSHOT_DELAY = 0.3
TIMEOUT_SECONDS = 30
POLL_INTERVAL = 0.1  # 100ms polling
MIN_HOTKEY_INTERVAL = 3

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
last_hotkey_time = {"cash": 0, "mtt": 0}

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
    global last_hotkey_time
    current_time = time.time()
    if current_time - last_hotkey_time[game_type] < MIN_HOTKEY_INTERVAL:
        logger.info(f"{game_type.upper()} hotkey throttled")
        return
    last_hotkey_time[game_type] = current_time
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

def is_hotkey_pressed(vk):
    """Check if a virtual key is currently pressed."""
    state = ctypes.windll.user32.GetAsyncKeyState(vk)
    return (state & 0x8000) != 0

def check_hotkeys():
    """Poll for hotkey combinations."""
    ctrl = is_hotkey_pressed(VK_CONTROL)
    shift = is_hotkey_pressed(VK_SHIFT)

    if ctrl and shift:
        if is_hotkey_pressed(VK_G):
            return 'cash'
        if is_hotkey_pressed(VK_M):
            return 'mtt'
    return None

def hotkey_poller():
    """Background thread that polls for hotkeys."""
    global running
    print("✅ 热键检测线程已启动")
    while running:
        game_type = check_hotkeys()
        if game_type:
            handle_hotkey(game_type)
        time.sleep(POLL_INTERVAL)
    print("热键检测线程已退出")

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

    # Start hotkey polling thread
    print("\n启动热键检测...")
    poller_thread = threading.Thread(target=hotkey_poller, daemon=True)
    poller_thread.start()

    print("等待热键按下... (切换到 GG Poker 窗口，按下 Ctrl+Shift+G 或 Ctrl+Shift+M)\n")

    try:
        while running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，退出...")
        running = False

    running = False
    print("退出。")

if __name__ == '__main__':
    main()
