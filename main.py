import cv2
import numpy as np
import mss
import time
import win32api
import win32con
import tkinter as tk
import json
import threading
import os
from tkinter import font
import sys
from concurrent.futures import ThreadPoolExecutor

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        # 获取打包时的临时目录路径
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 配置文件路径
TEMPLATES_FILE = resource_path("templates.json")
ROI = {"top": 900, "left": 0, "width": 2560, "height": 550}

# 加载所有英雄模板
def load_all_heroes():
    with open(TEMPLATES_FILE, "r",encoding='utf-8') as file:
        templates = json.load(file)
    all_heroes = {}
    for stage, heroes in templates.items():
        all_heroes[stage]=heroes
    return all_heroes

# 英雄模板路径
TEMPLATES = {}
templates_changed = threading.Event()  # 用于检测模板改变的事件

def capture_screen(region):
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        return cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2RGB)
        # return cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2GRAY)

def match_hero(template_path, screenshot, threshold=0.6):
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        raise ValueError(f"无法加载模板图片：{template_path}")
    # 模板匹配
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val > threshold:
        h, w,_ = template.shape
        matched_image = screenshot[max_loc[1]:max_loc[1] + h, max_loc[0]:max_loc[0] + w]
        return max_loc, matched_image
    else:
        return None, None



def is_greyscale_image(image, threshold=0.8, tolerance=20):
    if image.ndim == 3:
        image=image.astype(np.int16)
        diff_rg = np.abs(image[:, :, 0] - image[:, :, 1])
        diff_gb = np.abs(image[:, :, 1] - image[:, :, 2])
        diff_rb = np.abs(image[:, :, 0] - image[:, :, 2])
        grey_pixels = (diff_rg <= tolerance) & (diff_gb <= tolerance) & (diff_rb <= tolerance)
    else:
        grey_pixels = np.ones(image.shape[:2], dtype=bool)
    grey_pixel_ratio = np.sum(grey_pixels) / grey_pixels.size
    return grey_pixel_ratio >= threshold

def click(x, y):
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

# 更新全局 TEMPLATES
def update_templates(selected_heroes, all_heroes):
    global TEMPLATES
    all_heroes_copy={}
    for category,heroes in all_heroes.items():
        for hero,j in heroes.items():
            all_heroes_copy[hero]=j
    TEMPLATES = {hero: all_heroes_copy[hero] for hero in selected_heroes}
    templates_changed.set()


def create_hero_selection_gui():
    all_heroes = load_all_heroes()
    selected_heroes = []

    def on_select(hero, var):
        if var.get():
            selected_heroes.append(hero)
        else:
            selected_heroes.remove(hero)
        update_templates(selected_heroes, all_heroes)
    def on_mouse_wheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    root = tk.Tk()
    root.iconbitmap(resource_path('image/avatar.ico'))
    root.title("选择英雄")
    root.geometry("400x600")
    root.attributes('-topmost', 1)
    default_font = font.nametofont("TkDefaultFont")
    default_font.configure(family="SimHei", size=12)
    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True)
    canvas = tk.Canvas(frame)
    scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollable_frame = tk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    for stage, heroes in all_heroes.items():
        stage_label = tk.Label(scrollable_frame, text=stage, font=("SimHei", 14, "bold"))
        stage_label.pack(anchor="w", padx=10, pady=5)
        for hero in heroes:
            var = tk.BooleanVar()
            checkbox = tk.Checkbutton(
                scrollable_frame,
                text=hero,
                variable=var,
                command=lambda h=hero, v=var: on_select(h, v)
            )
            checkbox.pack(anchor="w", padx=20)
    frame.bind_all("<MouseWheel>", on_mouse_wheel)
    def on_close():
        global running
        running=False
        root.quit()
        root.destroy()
        sys.exit()
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

def match_all_heroes(templates, screenshot):
    results = {}
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(match_hero, resource_path(template_path), screenshot): hero
            for hero, template_path in templates.items()
        }
        for future in futures:
            hero = futures[future]
            match, matched_image = future.result()
            if match:
                results[hero] = (match, matched_image)
    return results

# 主循环
def main_loop():
    while running:
        screenshot = capture_screen(ROI)
        results = match_all_heroes(TEMPLATES, screenshot)
        for hero, (match, matched_image) in results.items():
            if match:
                if is_greyscale_image(matched_image):
                    break
                x, y = match[0] + ROI["left"]+100, match[1] + ROI["top"]+100
                click(x, y)
                time.sleep(0.1)
                break

running=True
# 启动 GUI 和主循环的线程
if __name__ == "__main__":
    gui_thread = threading.Thread(target=create_hero_selection_gui)
    gui_thread.start()
    main_loop()
