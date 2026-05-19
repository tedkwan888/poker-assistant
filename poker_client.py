#!/usr/bin/env python3
"""
Poker Assistant Windows Client
Global hotkey -> screenshot -> send to server -> display result
"""

import sys
import os
import time
import logging
import tempfile
import ctypes

import pyautogui
import pynput
from pynput import keyboard
import requests

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
    return f"{icon} 【{game_type.upper()} 分析结果】\n\n{advice}\n\nID: {result.get('id', 'N/A')}"

def handle_hotkey(game_type):
    global last_screenshot_time
    current_time = time.time()
    if current_time - last_screenshot_time < MIN_HOTKEY_INTERVAL:
        logger.info("Hotkey throttled")
        return
    last_screenshot_time = current_time
    mode = "CASH" if game_type == 'cash' else "MTT"
    logger.info(f"=== {mode} HOTKEY TRIGGERED ===")
    time.sleep(SCREENSHOT_DELAY)
    img_path = take_screenshot()
    if not img_path:
        print("截图失败")
        return
    result = send_to_server(img_path, game_type)
    print(format_analysis_response(result))

class HotkeyListener:
    def __init__(self):
        self.ctrl_pressed = False
        self.shift_pressed = False
        self.listener = None

    def start(self):
        def on_press(key):
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.ctrl_pressed = True
                elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                    self.shift_pressed = True
                if self.ctrl_pressed and self.shift_pressed:
                    if hasattr(key, 'char') and key.char:
                        if key.char.lower() == 'g':
                            handle_hotkey('cash')
                        elif key.char.lower() == 'm':
                            handle_hotkey('mtt')
            except Exception as e:
                logger.error(f"Hotkey press error: {e}")

        def on_release(key):
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.ctrl_pressed = False
                elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                    self.shift_pressed = False
            except:
                pass

        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.start()
        logger.info("Hotkey listener started")

    def stop(self):
        if self.listener:
            self.listener.stop()

def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║       POKER ASSISTANT - WINDOWS CLIENT              ║
╠══════════════════════════════════════════════════════╣
║  Ctrl+Shift+G  ->  Cash Game 分析                   ║
║  Ctrl+Shift+M  ->  MTT Tournament 分析              ║
║                                                      ║
║  Server:  183.179.89.122:5199                       ║
║  Status:  Connected                                  ║
╠══════════════════════════════════════════════════════╣
║  Press Ctrl+C to exit                                ║
╚══════════════════════════════════════════════════════╝
    """)

def main():
    global running
    if not is_admin():
        print("建议以管理员身份运行以确保热键正常工作")
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.1
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"Server connected: {SERVER_URL}")
    except Exception as e:
        print(f"Cannot connect to server: {e}")
        sys.exit(1)
    listener = HotkeyListener()
    listener.start()
    print_banner()
    print("等待热键按下...")
    try:
        while running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nExiting...")
        running = False
        listener.stop()
        sys.exit(0)

if __name__ == '__main__':
    main()
