import pygame
import sys
import os
from PIL import Image
import random
import tkinter as tk
from tkinter import filedialog

# 初始化 Pygame 和音频模块
pygame.init()
pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)

# 屏幕设置
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 850
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("氷上メルル模拟器")

# === 添加缺失的全局变量 ===
TOTAL_TIME_MS = 60000  # 默认游戏时长 60 秒
# =========================

# 颜色定义
BACKGROUND = (240, 240, 245)
PANEL_BG = (255, 255, 255)
BUTTON_NORMAL = (70, 130, 180)
BUTTON_HOVER = (100, 160, 210)
BUTTON_CLICK = (50, 110, 160)
BUTTON_DISABLED = (180, 180, 180)
TEXT_COLOR = (50, 50, 50)
GRID_LINE = (200, 200, 200)
EMPTY_TILE = (230, 230, 230)
SUCCESS_COLOR = (76, 175, 80)
FAIL_TEXT_COLOR = (220, 50, 50)
GRID_COLOR = (220, 220, 220)
WARNING_FLASH_COLOR = (255, 0, 0, 150)  # 半透明红色用于警告闪烁
PROGRESS_BAR_BG = (200, 200, 200)
PROGRESS_BAR_FG = (255, 140, 0)  # 橙色
SLIDER_BG = (200, 200, 200)
SLIDER_FG = (100, 160, 210)
SETTING_PANEL_BG = (245, 245, 250)  # 设置面板稍深一点
MODAL_OVERLAY_COLOR = (0, 0, 0, 128)  # 50% 不透明度的黑色

# === 字体：优先使用同目录下的 SourceHanSerifSC.otf ===
def get_custom_font(size):
    font_path = os.path.join(os.path.dirname(__file__), "SourceHanSerifSC.otf")
    if os.path.exists(font_path):
        try:
            return pygame.font.Font(font_path, size)
        except Exception as e:
            print(f"无法加载自定义字体: {e}")
    # 回退到系统字体
    font_names = ['simhei', 'Microsoft YaHei', 'PingFang', 'STHeiti', 'Arial Unicode MS', 'sans']
    for name in font_names:
        path = pygame.font.match_font(name)
        if path:
            try:
                return pygame.font.Font(path, size)
            except:
                continue
    return pygame.font.SysFont(None, size)

font_large = get_custom_font(36)
font_medium = get_custom_font(24)
font_small = get_custom_font(18)
font_fail = get_custom_font(64)  # 增大失败字体
font_intro_title = get_custom_font(48)  # 开场标题字体

# === 音频与倒计时常量 ===
# --- 默认值 ---
DEFAULT_TOTAL_TIME_KEY = "15m"
DEFAULT_MUSIC_VOLUME = 0.6  # 60%
# --- 可选的总时间配置 ---
TIME_OPTIONS = {
    "30s": 30 * 1000,      # 30 秒
    "5m": 5 * 60 * 1000,   # 5 分钟
    "10m": 10 * 60 * 1000, # 10 分钟
    "15m": 15 * 60 * 1000  # 15 分钟
}
MUSIC_FADEIN_DURATION = 2000  # 淡入2秒
MUSIC_FADEOUT_DURATION = 1000  # 淡出1秒
MUSIC_VOLUME_TARGET = DEFAULT_MUSIC_VOLUME  # 初始目标音量
WARNING_FLASH_START_MS = 10 * 1000  # 10秒开始警告闪烁
INTRO_MUSIC_VOLUME = 0.5  # 开场音乐音量

# 游戏状态枚举
STATE_INTRO = "intro"
STATE_GAME = "game"
STATE_FAIL = "fail"

class Button:
    def __init__(self, x, y, width, height, text, callback=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.hover = False
        self.clicked = False
        self.enabled = True
        self.visible = True
        self.selected = False  # 新增 selected 状态

    def draw(self, screen):
        if not self.visible:
            return
        if not self.enabled:
            color = BUTTON_DISABLED
        elif self.clicked or self.selected:  # 优先显示 clicked 或 selected 状态
            color = BUTTON_CLICK
        elif self.hover:
            color = BUTTON_HOVER
        else:
            color = BUTTON_NORMAL

        pygame.draw.rect(screen, color, self.rect, border_radius=5)
        pygame.draw.rect(screen, (150, 150, 150), self.rect, 2, border_radius=5)

        text_color = (255, 255, 255) if self.enabled else (220, 220, 220)
        text_surface = font_medium.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

    def handle_event(self, event):
        if not self.enabled or not self.visible:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.clicked = True
                return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.clicked:
                self.clicked = False
                if self.callback:
                    self.callback()
                return True
        self.clicked = False
        return False

class Slider:
    def __init__(self, x, y, width, height, min_val, max_val, initial_val, label=""):
        self.rect = pygame.Rect(x, y, width, height)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.label = label
        self.dragging = False
        self.knob_radius = height // 2 + 2
        self.knob_pos = self.value_to_pos(initial_val)

    def value_to_pos(self, val):
        ratio = (val - self.min_val) / (self.max_val - self.min_val) if self.max_val != self.min_val else 0
        return self.rect.x + int(ratio * self.rect.width)

    def pos_to_value(self, pos):
        ratio = (pos - self.rect.x) / self.rect.width if self.rect.width > 0 else 0
        ratio = max(0, min(1, ratio))  # Clamp between 0 and 1
        return self.min_val + ratio * (self.max_val - self.min_val)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_x, mouse_y = event.pos
            knob_rect = pygame.Rect(
                self.knob_pos - self.knob_radius,
                self.rect.y - self.knob_radius,
                self.knob_radius * 2,
                self.knob_radius * 2
            )
            if knob_rect.collidepoint(mouse_x, mouse_y):
                self.dragging = True
            elif self.rect.collidepoint(mouse_x, mouse_y):  # Click on the slider bar to jump
                self.value = self.pos_to_value(mouse_x)
                self.knob_pos = mouse_x
                self.dragging = True
            return True  # Value changed
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            mouse_x, _ = event.pos
            self.value = self.pos_to_value(mouse_x)
            self.knob_pos = max(self.rect.x, min(self.rect.x + self.rect.width, mouse_x))
            return True  # Value changed during drag
        return False  # No change

    def draw(self, screen):
        # Draw track
        pygame.draw.rect(screen, SLIDER_BG, self.rect)
        # Draw filled part
        fill_width = self.knob_pos - self.rect.x
        if fill_width > 0:
            fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_width, self.rect.height)
            pygame.draw.rect(screen, SLIDER_FG, fill_rect)
        # Draw border
        pygame.draw.rect(screen, (150, 150, 150), self.rect, 1)
        # Draw knob
        pygame.draw.circle(screen, (255, 255, 255), (self.knob_pos, self.rect.centery), self.knob_radius)
        pygame.draw.circle(screen, (100, 100, 100), (self.knob_pos, self.rect.centery), self.knob_radius, 2)
        # Draw label and value
        if self.label:
            label_surface = font_small.render(self.label, True, TEXT_COLOR)
            screen.blit(label_surface, (self.rect.x, self.rect.y - 25))
            value_text = f"{self.value:.0%}"  # 显示为百分比
            value_surface = font_small.render(value_text, True, TEXT_COLOR)
            screen.blit(value_surface, (self.rect.x + self.rect.width - value_surface.get_width(), self.rect.y - 25))


class SettingsPanel:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.visible = False
        # 返回按钮放置在右下角更合理
        self.back_button = Button(x + width - 100, y + height - 50, 80, 35, "返回")
        self.back_button.callback = self.hide  # 设置返回按钮的回调为隐藏自身

        # 音量滑块
        slider_x = x + 20
        slider_y = y + 60
        self.volume_slider = Slider(slider_x, slider_y, width - 40, 20, 0.0, 1.0, DEFAULT_MUSIC_VOLUME, "背景音乐音量")

        # 时间选项按钮
        timer_y = slider_y + 60
        self.timer_buttons = []
        options = list(TIME_OPTIONS.keys())
        btn_width = (width - 50) // len(options)  # 动态计算按钮宽度
        for i, key in enumerate(options):
            btn_x = slider_x + i * (btn_width + 10)
            # 按钮文本使用键作为标签，例如 "30s" -> "30秒"
            display_text = {"30s": "30秒", "5m": "5分钟", "10m": "10分钟", "15m": "15分钟"}.get(key, key)
            btn = Button(btn_x, timer_y, btn_width, 30, display_text)
            btn.time_key = key
            btn.selected = (key == DEFAULT_TOTAL_TIME_KEY)  # 默认选中项
            btn.callback = lambda k=key: self.select_time(k)  # 使用默认参数捕获
            self.timer_buttons.append(btn)

        # 标题
        self.title_surface = font_medium.render("设置", True, TEXT_COLOR)
        self.title_pos = (self.rect.x + 20, self.rect.y + 15)

    def select_time(self, key):
        """选择倒计时时长"""
        global TOTAL_TIME_MS  # 修改全局变量
        TOTAL_TIME_MS = TIME_OPTIONS[key]
        # 更新按钮选中状态
        for btn in self.timer_buttons:
            btn.selected = (btn.time_key == key)
        print(f"倒计时已设置为: {key} ({TOTAL_TIME_MS}ms)")

    def show(self):
        """显示设置面板"""
        self.visible = True

    def hide(self):
        """隐藏设置面板"""
        self.visible = False

    def handle_event(self, event):
        if not self.visible:
            return False

        # 处理滑块事件
        volume_changed = self.volume_slider.handle_event(event)
        if volume_changed:
            # 实时更新音乐音量
            pygame.mixer.music.set_volume(self.volume_slider.value)
            # 如果有失败音效且正在播放，也尝试更新其音量（注意：pygame Sound 对象的 set_volume 是独立的）
            # 这里只更新主音乐音量

        # 处理按钮事件
        for btn in self.timer_buttons:
            btn.handle_event(event)

        back_clicked = self.back_button.handle_event(event)
        if back_clicked:
            self.hide()
            return True  # 消费事件

        # 如果点击了面板外部（模态对话框行为），则关闭
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.hide()
                return True  # 消费事件

        return False  # No event consumed

    def draw(self, screen):
        if not self.visible:
            return

        # 绘制半透明背景 (模态效果)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill(MODAL_OVERLAY_COLOR)
        screen.blit(overlay, (0, 0))

        # Draw panel background
        pygame.draw.rect(screen, SETTING_PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(screen, (180, 180, 180), self.rect, 2, border_radius=10)

        # Draw title
        screen.blit(self.title_surface, self.title_pos)

        # Draw components
        self.volume_slider.draw(screen)
        for btn in self.timer_buttons:
            btn.draw(screen)
        self.back_button.draw(screen) # 绘制返回按钮

    def set_volume(self, volume):
        """外部设置滑块值"""
        self.volume_slider.value = volume
        self.volume_slider.knob_pos = self.volume_slider.value_to_pos(volume)

    def get_selected_time_key(self):
        """获取当前选中的时间键"""
        for btn in self.timer_buttons:
            if btn.selected:
                return btn.time_key
        return DEFAULT_TOTAL_TIME_KEY  # Fallback


class PuzzleGame:
    def __init__(self):
        self.original_image = None
        self.cropped_image = None
        self.puzzle_pieces = []
        self.grid_size = 3
        self.puzzle_grid = []
        self.empty_pos = (0, 0)
        self.moves = 0
        self.game_started = False
        self.solved = False
        self.timer_started = False
        self.start_time_ms = 0
        # === 使用全局变量初始化 ===
        self.remaining_time_ms = TOTAL_TIME_MS
        # ========================
        self.music_fading_in = False
        self.music_fading_out = False
        self.music_volume = 0.0
        self.piece_images = []
        self.puzzle_area = pygame.Rect(600, 100, 500, 500)
        self.image_area = pygame.Rect(50, 100, 400, 400)
        self.warning_flash_active = False
        self.last_warning_flash_time = 0
        self.warning_flash_interval = 500  # 0.5秒闪烁一次
        self.create_buttons()
        # 加载开场和失败图片 (保留Alpha通道)
        self.intro_image = self.load_pygame_image("1-5-7_Meruru.png", (821, 1073), keep_alpha=True)
        self.fail_bg_image = self.load_pygame_image("Still_430_002.png", (4096, 2048), keep_alpha=False)  # 背景通常不需要alpha

        # 缩放开场图以适应屏幕，并为标题留出空间
        if self.intro_image:
            img_w, img_h = self.intro_image.get_size()
            # 计算可用于图片的最大高度（屏幕高度减去上下边距和标题高度及间距）
            available_height = SCREEN_HEIGHT - 2 * 50 - 100  # 50px 上下边距, 100px 标题和间距
            if img_h > available_height:
                scale = available_height / img_h
            else:  # 如果图片本身不大于可用空间，则按比例放大，但最大不超过屏幕高度的80%
                scale = min(1.0, SCREEN_HEIGHT / img_h * 0.8)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            self.intro_scaled = pygame.transform.smoothscale(self.intro_image, (new_w, new_h))
        else:
            self.intro_scaled = None

        # 缩放失败背景图以填满屏幕（居中裁剪）
        if self.fail_bg_image:
            img_w, img_h = self.fail_bg_image.get_size()
            # 先缩放到至少覆盖屏幕
            scale_x = SCREEN_WIDTH / img_w
            scale_y = SCREEN_HEIGHT / img_h
            scale = max(scale_x, scale_y)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            scaled = pygame.transform.smoothscale(self.fail_bg_image, (new_w, new_h))
            # 裁剪居中
            crop_x = (new_w - SCREEN_WIDTH) // 2
            crop_y = (new_h - SCREEN_HEIGHT) // 2
            self.fail_bg_scaled = scaled.subsurface((crop_x, crop_y, SCREEN_WIDTH, SCREEN_HEIGHT))
        else:
            self.fail_bg_scaled = None

        # 加载失败音效
        self.fail_sound = None
        self.fail_sound_path = os.path.join(os.path.dirname(__file__), "0105Adv09_Ema061.ogg")
        if os.path.exists(self.fail_sound_path):
            try:
                self.fail_sound = pygame.mixer.Sound(self.fail_sound_path)
            except Exception as e:
                print(f"加载失败音效失败: {e}")
        else:
            print("警告：未找到失败音效 0105Adv09_Ema061.ogg")
        self.last_fail_sound_play_time = 0
        self.fail_sound_interval = 1000  # 1秒间隔

        # 加载开场音乐路径
        self.intro_music_path = os.path.join(os.path.dirname(__file__), "Bgm_036_001_Loop.ogg")

    def load_pygame_image(self, filename, expected_size=None, keep_alpha=False):
        path = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(path):
            print(f"警告：未找到图片 {filename}")
            return None
        try:
            pil_img = Image.open(path)
            # 不再强制转换为 RGB，保留 Alpha 通道
            if expected_size:
                pil_img = pil_img.resize(expected_size, Image.LANCZOS)
            mode = pil_img.mode
            size = pil_img.size
            data = pil_img.tobytes()
            if mode in ('RGB', 'RGBA'):
                format_string = mode
            elif mode == 'P' and 'transparency' in pil_img.info:
                # 如果是带透明度的调色板模式，转换为 RGBA
                pil_img = pil_img.convert('RGBA')
                mode = 'RGBA'
                data = pil_img.tobytes()
                format_string = mode
            else:
                # 对于其他不支持的模式，转换为 RGB 或 RGBA
                if keep_alpha and pil_img.mode.endswith('A'):
                    pil_img = pil_img.convert('RGBA')
                    format_string = 'RGBA'
                else:
                    pil_img = pil_img.convert('RGB')
                    format_string = 'RGB'
                data = pil_img.tobytes()
            return pygame.image.fromstring(data, size, format_string)
        except Exception as e:
            print(f"加载图片 {filename} 失败: {e}")
            return None

    def create_buttons(self):
        button_width = 180
        button_height = 40
        button_x = 50
        button_y = 520
        self.upload_btn = Button(button_x, button_y, button_width, button_height, "上传图片", self.open_file_dialog)
        self.generate_btn = Button(button_x, button_y + 60, button_width, button_height, "生成拼图", self.generate_puzzle)
        self.generate_btn.enabled = False
        self.shuffle_btn = Button(button_x, button_y + 120, button_width, button_height, "重新打乱", self.shuffle_puzzle)
        self.shuffle_btn.enabled = False
        self.solve_btn = Button(button_x, button_y + 180, button_width, button_height, "一键复原", self.solve_puzzle)
        self.solve_btn.enabled = False
        self.size_buttons = []
        sizes = [3, 4, 5, 6]
        size_btn_width = 60
        for i, size in enumerate(sizes):
            x_pos = button_x + 200 + i * (size_btn_width + 10)
            btn = Button(x_pos, button_y, size_btn_width, button_height, f"{size}×{size}")
            btn.size = size
            btn.selected = (size == 3)
            btn.callback = lambda s=size: self.select_grid_size(s)
            self.size_buttons.append(btn)

    def select_grid_size(self, size):
        self.grid_size = size
        for btn in self.size_buttons:
            btn.selected = (btn.size == size)
        if self.cropped_image:
            self.generate_puzzle()

    def open_file_dialog(self):
        root = tk.Tk()
        root.withdraw()
        filetypes = [("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"), ("所有文件", "*.*")]
        filepath = filedialog.askopenfilename(title="选择图片", filetypes=filetypes)
        root.destroy()
        if filepath:
            self.load_image(filepath)

    def load_image(self, filepath):
        try:
            img = Image.open(filepath)
            # 保留 Alpha 通道，只在裁剪/缩放时转换为 RGBA 以便操作
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            width, height = img.size
            min_dim = min(width, height)
            left = (width - min_dim) // 2
            top = (height - min_dim) // 2
            right = left + min_dim
            bottom = top + min_dim
            cropped_img = img.crop((left, top, right, bottom))
            display_size = 400
            cropped_img = cropped_img.resize((display_size, display_size), Image.LANCZOS)
            self.original_image = cropped_img
            self.cropped_image = self.pil_to_pygame(cropped_img)
            self.generate_btn.enabled = True
            return True
        except Exception as e:
            print(f"加载图片失败: {e}")
            return False

    def pil_to_pygame(self, pil_image):
        mode = pil_image.mode
        size = pil_image.size
        data = pil_image.tobytes()
        # 直接从 PIL 图像创建 Pygame Surface，保留 Alpha
        if mode in ("RGB", "RGBA"):
            return pygame.image.fromstring(data, size, mode)
        else:
            # 如果之前转成了 RGBA，则这里也是 RGBA
            rgba_image = pil_image.convert("RGBA")
            data = rgba_image.tobytes()
            return pygame.image.fromstring(data, size, "RGBA")

    def generate_puzzle(self):
        if self.cropped_image is None:
            return
        self.puzzle_pieces = []
        self.piece_images = []
        self.puzzle_grid = []
        self.game_started = True
        self.solved = False
        self.moves = 0
        self.timer_started = False
        self.music_fading_in = False
        self.music_fading_out = False
        self.music_volume = 0.0
        self.warning_flash_active = False
        self.last_warning_flash_time = 0
        # === 使用全局变量初始化 ===
        self.remaining_time_ms = TOTAL_TIME_MS
        # ========================
        pygame.mixer.music.stop()  # 确保在生成新拼图时停止任何可能存在的音乐

        piece_size = self.cropped_image.get_width() // self.grid_size
        pieces = []
        for row in range(self.grid_size):
            piece_row = []
            for col in range(self.grid_size):
                rect = pygame.Rect(col * piece_size, row * piece_size, piece_size, piece_size)
                # 使用带 Alpha 的 Surface
                piece_surface = pygame.Surface((piece_size, piece_size), pygame.SRCALPHA)
                piece_surface.blit(self.cropped_image, (0, 0), rect)
                pygame.draw.rect(piece_surface, (200, 200, 200), (0, 0, piece_size, piece_size), 1)
                piece_row.append(piece_surface)
            pieces.append(piece_row)
        self.puzzle_pieces = pieces
        self.initialize_puzzle_grid()
        self.shuffle_btn.enabled = True
        self.solve_btn.enabled = True

    def initialize_puzzle_grid(self):
        numbers = list(range(1, self.grid_size * self.grid_size)) + [None]
        self.puzzle_grid = []
        idx = 0
        for i in range(self.grid_size):
            row = []
            for j in range(self.grid_size):
                row.append(numbers[idx])
                idx += 1
            self.puzzle_grid.append(row)
        self.empty_pos = (self.grid_size - 1, self.grid_size - 1)
        self.create_piece_rects()

    def create_piece_rects(self):
        self.piece_images = []
        cell_size = min(self.puzzle_area.width, self.puzzle_area.height) // self.grid_size
        start_x = self.puzzle_area.x + (self.puzzle_area.width - cell_size * self.grid_size) // 2
        start_y = self.puzzle_area.y + (self.puzzle_area.height - cell_size * self.grid_size) // 2
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                piece_num = self.puzzle_grid[row][col]
                if piece_num is not None:
                    original_row = (piece_num - 1) // self.grid_size
                    original_col = (piece_num - 1) % self.grid_size
                    piece_image = self.puzzle_pieces[original_row][original_col]
                    scaled_piece = pygame.transform.smoothscale(piece_image, (cell_size, cell_size))
                    rect = pygame.Rect(
                        start_x + col * cell_size,
                        start_y + row * cell_size,
                        cell_size,
                        cell_size
                    )
                    self.piece_images.append({
                        'image': scaled_piece,
                        'rect': rect,
                        'grid_pos': (row, col),
                        'number': piece_num
                    })

    def shuffle_puzzle(self, moves=100):
        if not self.game_started:
            return
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        for _ in range(moves):
            valid_moves = []
            for dr, dc in directions:
                new_row, new_col = self.empty_pos[0] + dr, self.empty_pos[1] + dc
                if 0 <= new_row < self.grid_size and 0 <= new_col < self.grid_size:
                    valid_moves.append((dr, dc))
            if valid_moves:
                dr, dc = random.choice(valid_moves)
                new_row, new_col = self.empty_pos[0] + dr, self.empty_pos[1] + dc
                self.puzzle_grid[self.empty_pos[0]][self.empty_pos[1]], self.puzzle_grid[new_row][new_col] = \
                    self.puzzle_grid[new_row][new_col], self.puzzle_grid[self.empty_pos[0]][self.empty_pos[1]]
                self.empty_pos = (new_row, new_col)
        self.solved = False
        self.moves = 0
        self.timer_started = False
        self.music_fading_in = False
        self.music_fading_out = False
        self.music_volume = 0.0
        self.warning_flash_active = False
        self.last_warning_flash_time = 0
        # === 使用全局变量初始化 ===
        self.remaining_time_ms = TOTAL_TIME_MS
        # ========================
        pygame.mixer.music.stop()  # 打乱时也停止音乐
        self.create_piece_rects()

    def move_piece(self, grid_pos):
        if self.solved or not self.game_started:
            return False
        row, col = grid_pos
        if (abs(row - self.empty_pos[0]) == 1 and col == self.empty_pos[1]) or \
           (abs(col - self.empty_pos[1]) == 1 and row == self.empty_pos[0]):
            self.puzzle_grid[row][col], self.puzzle_grid[self.empty_pos[0]][self.empty_pos[1]] = \
                self.puzzle_grid[self.empty_pos[0]][self.empty_pos[1]], self.puzzle_grid[row][col]
            self.empty_pos = (row, col)
            self.moves += 1
            if not self.timer_started:
                self.timer_started = True
                self.start_time_ms = pygame.time.get_ticks()
                self.music_fading_in = True
                self.music_volume = 0.0
                music_path = os.path.join(os.path.dirname(__file__), "Bgm_015_001_Loop.ogg")
                if os.path.exists(music_path):
                    pygame.mixer.music.load(music_path)
                    pygame.mixer.music.play(-1)  # 应用当前设置的音量
                    pygame.mixer.music.set_volume(settings_panel.volume_slider.value)
                else:
                    print("警告：未找到背景音乐 Bgm_015_001_Loop.ogg")
            self.create_piece_rects()
            self.solved = self.check_solution()
            if self.solved:
                self.handle_solve()
            return True
        return False

    def handle_solve(self):
        self.solved = True
        if pygame.mixer.music.get_busy():
            self.music_fading_out = True
            self.music_fading_in = False

    def check_solution(self):
        expected = 1
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if i == self.grid_size - 1 and j == self.grid_size - 1:
                    if self.puzzle_grid[i][j] is not None:
                        return False
                else:
                    if self.puzzle_grid[i][j] != expected:
                        return False
                    expected += 1
        return True

    def solve_puzzle(self):
        if not self.game_started:
            return
        solved_grid = []
        num = 1
        for i in range(self.grid_size):
            row = []
            for j in range(self.grid_size):
                if i == self.grid_size - 1 and j == self.grid_size - 1:
                    row.append(None)
                else:
                    row.append(num)
                    num += 1
            solved_grid.append(row)
        self.puzzle_grid = solved_grid
        self.empty_pos = (self.grid_size - 1, self.grid_size - 1)
        self.handle_solve()
        self.create_piece_rects()

    def reset_game(self):
        """重置游戏状态，回到初始准备状态"""
        self.cropped_image = None
        self.original_image = None
        self.game_started = False
        self.solved = False
        self.moves = 0
        self.timer_started = False
        # === 使用全局变量初始化 ===
        self.remaining_time_ms = TOTAL_TIME_MS
        # ========================
        self.generate_btn.enabled = False
        self.shuffle_btn.enabled = False
        self.solve_btn.enabled = False
        self.warning_flash_active = False
        self.last_warning_flash_time = 0
        pygame.mixer.music.stop()  # 重置时停止音乐
        # 停止失败音效
        if self.fail_sound:
            self.fail_sound.stop()
        self.last_fail_sound_play_time = 0

    def update_music(self, dt_ms):
        # MUSIC_VOLUME_TARGET 现在动态等于滑块值
        current_target_volume = settings_panel.volume_slider.value
        if self.music_fading_in:
            self.music_volume += (current_target_volume / MUSIC_FADEIN_DURATION) * dt_ms
            if self.music_volume >= current_target_volume:
                self.music_volume = current_target_volume
                self.music_fading_in = False
            pygame.mixer.music.set_volume(self.music_volume)
        elif self.music_fading_out:
            self.music_volume -= (current_target_volume / MUSIC_FADEOUT_DURATION) * dt_ms
            if self.music_volume <= 0:
                self.music_volume = 0
                self.music_fading_out = False
                pygame.mixer.music.stop()  # 淡出完成后完全停止音乐
            pygame.mixer.music.set_volume(self.music_volume)

    def update_warnings(self, current_time):
        """更新警告状态，如闪烁等"""
        if self.timer_started and not self.solved:
            elapsed = current_time - self.start_time_ms
            self.remaining_time_ms = max(0, TOTAL_TIME_MS - elapsed)  # 使用全局变量
            # 检查是否需要开始警告闪烁
            if self.remaining_time_ms <= WARNING_FLASH_START_MS:
                if current_time - self.last_warning_flash_time > self.warning_flash_interval:
                    self.warning_flash_active = not self.warning_flash_active
                    self.last_warning_flash_time = current_time
            else:
                self.warning_flash_active = False  # 重置状态
        else:
            self.warning_flash_active = False

    def draw(self, screen):
        screen.fill(BACKGROUND)
        title_text = font_large.render("氷上メルル模拟器", True, TEXT_COLOR)
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 30))

        # 左侧原始图片
        pygame.draw.rect(screen, PANEL_BG, self.image_area, border_radius=10)
        pygame.draw.rect(screen, GRID_COLOR, self.image_area, 2, border_radius=10)
        if self.cropped_image:
            img_width, img_height = self.cropped_image.get_size()
            img_x = self.image_area.x + (self.image_area.width - img_width) // 2
            img_y = self.image_area.y + (self.image_area.height - img_height) // 2
            screen.blit(self.cropped_image, (img_x, img_y))
        else:
            hint_text = font_medium.render("请上传图片", True, (150, 150, 150))
            screen.blit(hint_text, (
                self.image_area.x + self.image_area.width // 2 - hint_text.get_width() // 2,
                self.image_area.y + self.image_area.height // 2 - hint_text.get_height() // 2
            ))
        left_title = font_medium.render("原始图片", True, TEXT_COLOR)
        screen.blit(left_title, (self.image_area.x + 20, self.image_area.y - 30))

        # 右侧拼图区域
        pygame.draw.rect(screen, PANEL_BG, self.puzzle_area, border_radius=10)
        pygame.draw.rect(screen, GRID_COLOR, self.puzzle_area, 2, border_radius=10)
        if self.game_started and not self.solved:
            cell_size = min(self.puzzle_area.width, self.puzzle_area.height) // self.grid_size
            start_x = self.puzzle_area.x + (self.puzzle_area.width - cell_size * self.grid_size) // 2
            start_y = self.puzzle_area.y + (self.puzzle_area.height - cell_size * self.grid_size) // 2
            for row in range(self.grid_size):
                for col in range(self.grid_size):
                    rect = pygame.Rect(start_x + col * cell_size, start_y + row * cell_size, cell_size, cell_size)
                    if (row, col) == self.empty_pos:
                        pygame.draw.rect(screen, EMPTY_TILE, rect)
                        pygame.draw.rect(screen, GRID_LINE, rect, 1)
            for piece in self.piece_images:
                screen.blit(piece['image'], piece['rect'])
                if self.grid_size <= 5:
                    number_text = font_small.render(str(piece['number']), True, TEXT_COLOR)
                    text_x = piece['rect'].x + piece['rect'].width // 2 - number_text.get_width() // 2
                    text_y = piece['rect'].y + 5
                    screen.blit(number_text, (text_x, text_y))
        elif self.solved:
            success_text = font_large.render("恭喜！拼图完成！", True, SUCCESS_COLOR)
            screen.blit(success_text, (
                self.puzzle_area.x + self.puzzle_area.width // 2 - success_text.get_width() // 2,
                self.puzzle_area.y + self.puzzle_area.height // 2 - success_text.get_height() // 2 - 20
            ))
            moves_text = font_medium.render(f"步数: {self.moves}", True, TEXT_COLOR)
            screen.blit(moves_text, (
                self.puzzle_area.x + self.puzzle_area.width // 2 - moves_text.get_width() // 2,
                self.puzzle_area.y + self.puzzle_area.height // 2 + 20
            ))
        else:
            hint_text = font_medium.render("请先上传图片并生成拼图", True, (150, 150, 150))
            screen.blit(hint_text, (
                self.puzzle_area.x + self.puzzle_area.width // 2 - hint_text.get_width() // 2,
                self.puzzle_area.y + self.puzzle_area.height // 2 - hint_text.get_height() // 2
            ))
        right_title = font_medium.render("拼图区域", True, TEXT_COLOR)
        screen.blit(right_title, (self.puzzle_area.x + 20, self.puzzle_area.y - 30))

        # 游戏状态信息
        if self.game_started:
            status_bg = pygame.Rect(
                self.puzzle_area.x,
                self.puzzle_area.y + self.puzzle_area.height + 20,
                self.puzzle_area.width,
                90
            )  # 增高一点容纳进度条
            pygame.draw.rect(screen, PANEL_BG, status_bg, border_radius=10)
            pygame.draw.rect(screen, GRID_COLOR, status_bg, 2, border_radius=10)
            if not self.solved:
                if self.timer_started:
                    elapsed = pygame.time.get_ticks() - self.start_time_ms
                    self.remaining_time_ms = max(0, TOTAL_TIME_MS - elapsed)  # 使用全局变量
                    if self.remaining_time_ms <= 0:  # 触发失败（由主循环处理状态切换）
                        pass
                    total_sec = self.remaining_time_ms // 1000
                    minutes = total_sec // 60
                    seconds = total_sec % 60
                    millis = self.remaining_time_ms % 1000
                    time_str = f"{minutes:02d}:{seconds:02d}.{millis:03d}"
                    moves_text = font_medium.render(f"移动步数: {self.moves}", True, TEXT_COLOR)
                    time_text = font_medium.render(f"倒计时: {time_str}", True, TEXT_COLOR)
                    # 绘制进度条和文字
                    progress_label = font_small.render("魔女杀手发动进度", True, TEXT_COLOR)
                    progress_ratio = min(elapsed / TOTAL_TIME_MS, 1.0) if TOTAL_TIME_MS > 0 else 0  # 使用全局变量
                    bar_width = int(status_bg.width * 0.8)
                    bar_height = 15
                    bar_x = status_bg.x + (status_bg.width - bar_width) // 2
                    bar_y = status_bg.y + status_bg.height - bar_height - 10
                    pygame.draw.rect(screen, PROGRESS_BAR_BG, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
                    pygame.draw.rect(screen, PROGRESS_BAR_FG, (bar_x, bar_y, int(bar_width * progress_ratio), bar_height), border_radius=5)
                    screen.blit(progress_label, (bar_x, bar_y - progress_label.get_height() - 5))
                else:
                    moves_text = font_medium.render(f"步数: {self.moves}", True, TEXT_COLOR)
                    time_text = font_medium.render("已完成！", True, SUCCESS_COLOR)
                    # 如果未开始计时，进度为0
                    progress_label = font_small.render("魔女杀手发动进度", True, TEXT_COLOR)
                    bar_width = int(status_bg.width * 0.8)
                    bar_height = 15
                    bar_x = status_bg.x + (status_bg.width - bar_width) // 2
                    bar_y = status_bg.y + status_bg.height - bar_height - 10
                    pygame.draw.rect(screen, PROGRESS_BAR_BG, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
                    screen.blit(progress_label, (bar_x, bar_y - progress_label.get_height() - 5))
                screen.blit(moves_text, (
                    status_bg.x + 20,
                    status_bg.y + 10  # 调整Y位置
                ))
                screen.blit(time_text, (
                    status_bg.x + status_bg.width - time_text.get_width() - 20,
                    status_bg.y + 10  # 调整Y位置
                ))
            else:  # 已经完成的情况
                moves_text = font_medium.render(f"步数: {self.moves}", True, TEXT_COLOR)
                time_text = font_medium.render("已完成！", True, SUCCESS_COLOR)
                # 进度为100%
                progress_label = font_small.render("魔女杀手发动进度", True, TEXT_COLOR)
                bar_width = int(status_bg.width * 0.8)
                bar_height = 15
                bar_x = status_bg.x + (status_bg.width - bar_width) // 2
                bar_y = status_bg.y + status_bg.height - bar_height - 10
                pygame.draw.rect(screen, PROGRESS_BAR_BG, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
                pygame.draw.rect(screen, PROGRESS_BAR_FG, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
                screen.blit(progress_label, (bar_x, bar_y - progress_label.get_height() - 5))
                screen.blit(moves_text, (
                    status_bg.x + 20,
                    status_bg.y + 10
                ))
                screen.blit(time_text, (
                    status_bg.x + status_bg.width - time_text.get_width() - 20,
                    status_bg.y + 10
                ))

        # 按钮和尺寸选择
        self.draw_buttons(screen)
        size_text = font_small.render("选择网格尺寸:", True, TEXT_COLOR)
        screen.blit(size_text, (50, 490))

        # 绘制警告闪烁效果 (在所有UI之上)
        if self.warning_flash_active:
            flash_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(flash_surface, WARNING_FLASH_COLOR, flash_surface.get_rect(), 15)  # 15px 宽的红色半透明边框
            screen.blit(flash_surface, (0, 0))

    def draw_buttons(self, screen):
        self.upload_btn.draw(screen)
        self.generate_btn.draw(screen)
        self.shuffle_btn.draw(screen)
        self.solve_btn.draw(screen)
        for btn in self.size_buttons:
            btn.draw(screen)

    def handle_events(self, event):
        self.upload_btn.handle_event(event)
        self.generate_btn.handle_event(event)
        self.shuffle_btn.handle_event(event)
        self.solve_btn.handle_event(event)
        for btn in self.size_buttons:
            btn.handle_event(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.game_started and not self.solved:
                for piece in self.piece_images:
                    if piece['rect'].collidepoint(event.pos):
                        self.move_piece(piece['grid_pos'])
                        break


# 创建设置面板实例 (放在游戏实例之前，因为它被游戏实例引用)
settings_panel = SettingsPanel(SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT // 2 - 150, 400, 300)

# 创建游戏实例
game = PuzzleGame()

# 主循环相关变量
clock = pygame.time.Clock()
running = True
last_time = pygame.time.get_ticks()

# 当前状态
current_state = STATE_INTRO

# 淡入控制
fade_alpha = 0
fade_speed = 255 / 1000  # 1秒淡入
fade_timer = 0

# 标记开场音乐是否已加载
intro_music_loaded = False

# === 替换原来的两个设置按钮为一个全局设置按钮 ===
settings_button = Button(SCREEN_WIDTH - 100, 20, 80, 35, "设置")
settings_button.callback = settings_panel.show

# 主循环相关变量
clock = pygame.time.Clock()
running = True
last_time = pygame.time.get_ticks()
current_state = STATE_INTRO
fade_alpha = 0
fade_speed = 255 / 1000
intro_music_loaded = False

# 主循环
while running:
    current_time = pygame.time.get_ticks()
    dt = current_time - last_time
    last_time = current_time

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # === 新增：让 settings_button 正常处理事件 ===
        if current_state in (STATE_INTRO, STATE_GAME):
            settings_button.handle_event(event)

        # === 设置面板优先处理事件（模态对话框）===
        if settings_panel.handle_event(event):
            continue  # 面板已消费事件，跳过后续处理

        # === 其他状态逻辑 ===
        if current_state == STATE_INTRO:
            # 点击任意非设置区域进入游戏（但要排除设置面板打开时）
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not settings_panel.visible and not settings_button.rect.collidepoint(event.pos):
                    pygame.mixer.music.stop()
                    intro_music_loaded = False
                    current_state = STATE_GAME
                    fade_alpha = 0

        elif current_state == STATE_GAME:
            game.handle_events(event)

        elif current_state == STATE_FAIL:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                current_state = STATE_GAME
                game.reset_game()
                fade_alpha = 0

    # === 状态逻辑 ===
    if current_state == STATE_INTRO:
        if not intro_music_loaded and os.path.exists(game.intro_music_path):
            try:
                pygame.mixer.music.load(game.intro_music_path)
                pygame.mixer.music.play(-1)
                pygame.mixer.music.set_volume(settings_panel.volume_slider.value)
                intro_music_loaded = True
            except Exception as e:
                print(f"加载开场音乐失败: {e}")
                intro_music_loaded = False

    elif current_state == STATE_GAME:
        if game.game_started and not game.solved and game.timer_started:
            elapsed = pygame.time.get_ticks() - game.start_time_ms
            if elapsed >= TOTAL_TIME_MS:
                current_state = STATE_FAIL
                fade_alpha = 0
                pygame.mixer.music.stop()
                game.music_fading_in = False
                game.music_fading_out = False
                game.music_volume = 0.0

    elif current_state == STATE_FAIL:
        pygame.mixer.music.stop()
        game.music_fading_in = False
        game.music_fading_out = False
        game.music_volume = 0.0
        if game.fail_sound:
            if current_time - game.last_fail_sound_play_time > game.fail_sound_interval:
                game.fail_sound.play()
                game.last_fail_sound_play_time = current_time

    # 更新游戏音乐和警告
    if current_state == STATE_GAME:
        game.update_music(dt)
        game.update_warnings(current_time)

    # 淡入效果
    if current_state in (STATE_INTRO, STATE_FAIL):
        fade_alpha = min(255, fade_alpha + fade_speed * dt)

    # 绘制
    screen.fill(BACKGROUND)

    if current_state == STATE_INTRO:
        if game.intro_scaled:
            img_w, img_h = game.intro_scaled.get_size()
            x = (SCREEN_WIDTH - img_w) // 2
            y = (SCREEN_HEIGHT - img_h) // 2
            temp_surf = game.intro_scaled.copy()
            temp_surf.set_alpha(int(fade_alpha))
            screen.blit(temp_surf, (x, y))
            title_text = "氷上メルル模拟器"
            text_surface = font_intro_title.render(title_text, True, TEXT_COLOR)
            text_x = SCREEN_WIDTH // 2 - text_surface.get_width() // 2
            text_y = y + img_h + 20
            screen.blit(text_surface, (text_x, text_y))
        else:
            text = font_large.render("点击任意位置开始", True, TEXT_COLOR)
            screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2))

        # === 绘制设置按钮（开场界面）===
        settings_button.draw(screen)

    elif current_state == STATE_FAIL:
        if game.fail_bg_scaled:
            temp_bg = game.fail_bg_scaled.copy()
            temp_bg.set_alpha(int(fade_alpha))
            screen.blit(temp_bg, (0, 0))
        else:
            screen.fill((0, 0, 0))
        fail_surface = font_fail.render("挑战失败！", True, FAIL_TEXT_COLOR)
        restart_surface = font_medium.render("点击任意位置重新开始", True, (255, 255, 255))
        screen.blit(fail_surface, (SCREEN_WIDTH//2 - fail_surface.get_width()//2, SCREEN_HEIGHT//2 - 40))
        screen.blit(restart_surface, (SCREEN_WIDTH//2 - restart_surface.get_width()//2, SCREEN_HEIGHT//2 + 40))

    elif current_state == STATE_GAME:
        game.draw(screen)
        # === 绘制设置按钮（游戏界面）===
        settings_button.draw(screen)

    # 最后绘制设置面板（确保在最上层）
    settings_panel.draw(screen)

    pygame.display.flip()
    clock.tick(60)

# 退出清理
pygame.mixer.music.stop()
if game.fail_sound:
    game.fail_sound.stop()
pygame.quit()
sys.exit()