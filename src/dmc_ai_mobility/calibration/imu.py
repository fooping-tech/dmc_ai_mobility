import time
import json
from pathlib import Path
from mpu9250_jmdev.registers import *
from mpu9250_jmdev.mpu_9250 import MPU9250

# MPU Setup
mpu = MPU9250(
    bus=1,
    address_mpu_master=0x68, 
    gfs=GFS_1000, 
    afs=AFS_8G, 
    mfs=AK8963_BIT_16, 
    mode=AK8963_MODE_C100HZ
)

print("Configuring MPU...")
try:
    # ここでエラーが出ても、ジャイロの設定が終わっていれば問題ないため無視します
    mpu.configure()
except OSError:
    print("\n[WARNING] Magnetometer (Compass) init failed.")
    print("Likely an MPU6500 (6-axis) device or connection issue.")
    print("Proceeding with Gyroscope calibration only (Safe for driving).\n")
except Exception as e:
    # その他のエラーは表示
    print(f"\n[ERROR] Unexpected error: {e}")
    print("Trying to proceed...\n")

print("keep the car STILL on a flat surface.")
print("Calibrating in 3 seconds...")
time.sleep(3)

print("Measuring...")
# 単純なオフセット計測
samples = 100
gx_sum, gy_sum, gz_sum = 0, 0, 0
success_count = 0

for i in range(samples):
    try:
        # ジャイロデータの取得
        data = mpu.readGyroscopeMaster()
        gx_sum += data[0]
        gy_sum += data[1]
        gz_sum += data[2]
        success_count += 1
    except Exception:
        # 読み取り失敗時はスキップ
        pass
    time.sleep(0.02)

if success_count > 0:
    offsets = {
        "gx_off": gx_sum / success_count,
        "gy_off": gy_sum / success_count,
        "gz_off": gz_sum / success_count
    }

    print("Calibration Result:", offsets)

    save_path = Path(__file__).resolve().parents[3] / "configs" / "imu_config.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with save_path.open("w", encoding="utf-8") as f:
        json.dump(offsets, f)
        
    print(f"Saved to {save_path}")
else:
    print("[ERROR] Could not read any data from Gyro.")
    print("Please check wiring (VCC, GND, SDA, SCL).")
