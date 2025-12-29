import json
import time
from pathlib import Path

from mpu9250_jmdev.registers import *
from mpu9250_jmdev.mpu_9250 import MPU9250

CONFIG_PATH = Path(__file__).resolve().parents[1] / "imu_config.json"


def load_offsets(path):
    offsets = {
        "gx_off": 0.0,
        "gy_off": 0.0,
        "gz_off": 0.0,
        "ax_off": 0.0,
        "ay_off": 0.0,
        "az_off": 0.0,
    }
    try:
        with path.open() as f:
            data = json.load(f)
        for key in offsets:
            if key in data:
                offsets[key] = float(data[key])
    except FileNotFoundError:
        print(f"Config not found: {path}, using zeros.")
    except (ValueError, TypeError, json.JSONDecodeError):
        print(f"Invalid config: {path}, using zeros.")
    return offsets


def create_mpu():
    mpu = MPU9250(
        bus=1,
        address_mpu_master=0x68,
        gfs=GFS_1000,
        afs=AFS_8G,
        mfs=AK8963_BIT_16,
        mode=AK8963_MODE_C100HZ,
    )
    try:
        mpu.configure()
    except OSError:
        print("[WARNING] Magnetometer init failed. Continuing without it.")
    except Exception as e:
        print(f"[WARNING] MPU configure error: {e}")
    return mpu


def read_calibrated_gyro(mpu, offsets):
    gx, gy, gz = mpu.readGyroscopeMaster()
    return (
        gx - offsets["gx_off"],
        gy - offsets["gy_off"],
        gz - offsets["gz_off"],
    )


def get_accel_reader(mpu):
    if hasattr(mpu, "readAccelerometerMaster"):
        return mpu.readAccelerometerMaster
    if hasattr(mpu, "readAccelerometer"):
        return mpu.readAccelerometer
    return None


def read_calibrated_accel(reader, offsets):
    ax, ay, az = reader()
    return (
        ax - offsets["ax_off"],
        ay - offsets["ay_off"],
        az - offsets["az_off"],
    )


def main():
    offsets = load_offsets(CONFIG_PATH)
    mpu = create_mpu()

    accel_reader = get_accel_reader(mpu)
    if accel_reader is None:
        print("Accelerometer read is not available in this MPU driver.")

    print("Reading IMU (Ctrl+C to stop)")
    while True:
        try:
            gx, gy, gz = read_calibrated_gyro(mpu, offsets)
            if accel_reader is not None:
                ax, ay, az = read_calibrated_accel(accel_reader, offsets)
                print(
                    f"gyro(dps) gx={gx:.3f} gy={gy:.3f} gz={gz:.3f} | "
                    f"accel(g) ax={ax:.3f} ay={ay:.3f} az={az:.3f}"
                )
            else:
                print(f"gyro(dps) gx={gx:.3f} gy={gy:.3f} gz={gz:.3f}")
        except Exception as e:
            print(f"Read error: {e}")
        time.sleep(0.2)


if __name__ == "__main__":
    main()
