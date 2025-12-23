#!/usr/bin/env python3
import time
import subprocess
import psutil
from PIL import Image, ImageDraw, ImageFont


# =========================
# CONFIG
# =========================
W, H = 320, 320

BAR_WIDTH = 315
BAR_HEIGHT = 40
BAR_RADIUS = BAR_HEIGHT // 2
BAR_X = 0

CPU_TEXT_Y = 32
BAR_CPU_Y  = 110
BAR_GPU_Y  = 162
GPU_TEXT_Y = 264

BG_COLOR = (0, 0, 0, 255)
BAR_BG = (190, 192, 196, 255)
CPU_FG = (80, 120, 255, 255)
GPU_FG = (190, 80, 220, 255)

TEXT_MAIN = (255, 255, 255, 255)
TEXT_SUB = (220, 220, 220, 255)

OUTPUT_PNG = "/home/giuseppe/Documenti/Progetti Python/liquidctl_new_project/img/logo.png"
LIQUIDCTL_CMD = ['liquidctl', '--match', 'Kraken', 'set', 'lcd', 'screen', 'static', OUTPUT_PNG]

# Interpolazione
REFRESH_S = 0.5          # ogni quanto aggiorni
SMOOTHING = 0.35         # 0..1 (più alto = più veloce verso il reale)
MAX_STEP = 4             # max gradi per step (limita “salti”)

# Font (Gotham SSm)
FONT_PATH = "/home/giuseppe/.local/share/fonts/GothamSSm/gothamnarrssm_black.otf"
font_label = ImageFont.truetype(FONT_PATH, 42)
font_temp_value = ImageFont.truetype(FONT_PATH, 132)
font_degree = ImageFont.truetype(FONT_PATH, 38)

# =========================
# FUNZIONI GRAFICHE
# =========================
def clamp(x, a, b):
    return max(a, min(b, x))

def temp_to_width(temp, max_width):
    temp = clamp(temp, 0, 100)
    return int((temp / 100) * max_width)

def draw_bar(draw, x, y, width, height, radius, bg_color, fg_color, value_width):
    draw.rounded_rectangle([x, y, x + width, y + height], radius=radius, fill=bg_color)
    if value_width > 0:
        draw.rounded_rectangle([x, y, x + value_width, y + height], radius=radius, fill=fg_color)

def draw_temp_with_degree(draw, right_x, y, temp_int, font_value, font_degree, fill,
                          degree_x_offset=0, degree_y_offset=20):
    value_str = str(int(temp_int))

    bbox_val = draw.textbbox((0, 0), value_str, font=font_value)
    val_w = bbox_val[2] - bbox_val[0]

    x_val = right_x - val_w
    draw.text((x_val, y), value_str, font=font_value, fill=fill)

    # simbolo °
    x_deg = right_x + degree_x_offset
    y_deg = y + degree_y_offset
    draw.text((x_deg, y_deg), "°", font=font_degree, fill=fill)

def render_frame(cpu_temp, gpu_temp):
    img = Image.new("RGBA", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    cpu_width = temp_to_width(cpu_temp, BAR_WIDTH)
    gpu_width = temp_to_width(gpu_temp, BAR_WIDTH)

    draw_bar(draw, BAR_X, BAR_CPU_Y, BAR_WIDTH, BAR_HEIGHT, BAR_RADIUS, BAR_BG, CPU_FG, cpu_width)
    draw_bar(draw, BAR_X, BAR_GPU_Y, BAR_WIDTH, BAR_HEIGHT, BAR_RADIUS, BAR_BG, GPU_FG, gpu_width)

    TEMP_RIGHT_EDGE = BAR_X + BAR_WIDTH - 10

    # Temperature (ancorate a destra) + simbolo °
    draw_temp_with_degree(draw, TEMP_RIGHT_EDGE, CPU_TEXT_Y - 60, cpu_temp,
                          font_temp_value, font_degree, TEXT_MAIN)

    draw_temp_with_degree(draw, TEMP_RIGHT_EDGE, GPU_TEXT_Y - 80, gpu_temp,
                          font_temp_value, font_degree, TEXT_MAIN)

    # Labels
    draw.text((BAR_X, CPU_TEXT_Y + 30), "CPU", font=font_label, fill=TEXT_SUB)
    draw.text((BAR_X, GPU_TEXT_Y - 60), "GPU", font=font_label, fill=TEXT_SUB)

    img.save(OUTPUT_PNG)

# =========================
# FUNZIONI TEMPERATURE (INT)
# =========================
def get_cpu_temp_int():
    temps = psutil.sensors_temperatures()
    if 'k10temp' in temps and temps['k10temp']:
        return int(round(temps['k10temp'][0].current))
    return None

def get_gpu_temp_int():
    temps = psutil.sensors_temperatures()
    if 'amdgpu' in temps:
        for t in temps['amdgpu']:
            if t.label == 'edge':
                return int(round(t.current))
    return None

# =========================
# INTERPOLAZIONE
# =========================
def smooth_step(display_val, target_val):
    """
    display_val -> target_val con smoothing + step max.
    Ritorna un INT.
    """
    if target_val is None:
        return display_val

    if display_val is None:
        return int(target_val)

    diff = target_val - display_val

    # avvicinamento morbido
    step = int(round(diff * SMOOTHING))

    # se lo smoothing produce 0 ma siamo lontani, muoviti di 1
    if step == 0 and diff != 0:
        step = 1 if diff > 0 else -1

    # limita i salti
    step = clamp(step, -MAX_STEP, MAX_STEP)

    return int(display_val + step)

# =========================
# IMPOSTAZIONE PRINCIPALE LCD
# =========================

def init_kraken():
    subprocess.run(
        ["liquidctl", "--match", "Kraken", "initialize"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def set_lcd_orientation():
    subprocess.run(
        ["liquidctl", "--match", "Kraken", "set", "lcd", "screen", "orientation", "270"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def set_lcd_brightness():
    subprocess.run(
        ["liquidctl", "--match", "Kraken", "set", "lcd", "screen", "brightness", "100"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

# =========================
# MAIN LOOP
# =========================
def main():

    time.sleep(2)
    init_kraken()

    set_lcd_orientation()
    set_lcd_brightness()

    cpu_disp = None
    gpu_disp = None

    while True:
        cpu_real = get_cpu_temp_int()
        gpu_real = get_gpu_temp_int()

        cpu_disp = smooth_step(cpu_disp, cpu_real)
        gpu_disp = smooth_step(gpu_disp, gpu_real)

        # clamp da 0 a 100 per la barra
        cpu_show = clamp(cpu_disp if cpu_disp is not None else 0, 0, 100)
        gpu_show = clamp(gpu_disp if gpu_disp is not None else 0, 0, 100)

        render_frame(cpu_show, gpu_show)

        # invia al Kraken
        try:
            subprocess.run(LIQUIDCTL_CMD, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        time.sleep(REFRESH_S)


if __name__ == "__main__":
    main()