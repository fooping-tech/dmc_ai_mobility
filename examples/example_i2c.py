import time
import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

# I2C Setup
i2c = busio.I2C(board.SCL, board.SDA)

# 1. OLED Setup
# 薄型OLED(128x32)の設定です。表示が崩れる場合は HEIGHT=64 を試してください。
WIDTH = 128
HEIGHT = 32
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C)

# --- 画面描画設定 (PIL使用) ---
oled.fill(0)
oled.show()

image = Image.new("1", (oled.width, oled.height))
draw = ImageDraw.Draw(image)

# フォント設定 (システムフォント DejaVuSansを使用)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except IOError:
    font = ImageFont.load_default()

# 表示位置調整 (32px高さを考慮)
TOP_MARGIN = 0 
LINE_HEIGHT = 16
SPINNER = ["-", "\\", "|", "/"]

start_time = time.time()
spinner_index = 0

try:
    while True:
        elapsed = int(time.time() - start_time)
        minutes, seconds = divmod(elapsed, 60)
        spinner = SPINNER[spinner_index % len(SPINNER)]
        spinner_index += 1

        # 描画クリア
        draw.rectangle((0, 0, oled.width, oled.height), outline=0, fill=0)

        # テキスト描画
        # 1行目: ロボット識別と状態
        draw.text((0, TOP_MARGIN), "DMC AI MOBILITY", font=font, fill=255)

        # 2行目: 稼働状況＋スピナー
        if HEIGHT >= 32:
            draw.text((0, TOP_MARGIN + LINE_HEIGHT), f"Uptime {minutes:02d}:{seconds:02d} {spinner}", font=font, fill=255)

        # 転送
        oled.image(image)
        oled.show()

        print(f"OLED updated, uptime {minutes:02d}:{seconds:02d}")
        time.sleep(1)

except KeyboardInterrupt:
    oled.fill(0)
    oled.show()
    print("Test finished")
