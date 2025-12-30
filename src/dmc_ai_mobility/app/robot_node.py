from __future__ import annotations

import json
import logging
import math
import threading
from pathlib import Path
from typing import Optional

from dmc_ai_mobility.core.config import RobotConfig
from dmc_ai_mobility.core.timing import PeriodicSleeper, monotonic_ms, wall_clock_ms
from dmc_ai_mobility.core.types import MotorCmd, OledCmd
from dmc_ai_mobility.drivers.camera_v4l2 import MockCameraDriver, OpenCVCameraConfig, OpenCVCameraDriver
from dmc_ai_mobility.drivers.imu import MockImuDriver, Mpu9250ImuDriver, MpuImuConfig
from dmc_ai_mobility.drivers.lidar import MockLidarDriver, YdLidarConfig, YdLidarDriver
from dmc_ai_mobility.drivers.motor import MockMotorDriver, PigpioMotorConfig, PigpioMotorDriver
from dmc_ai_mobility.drivers.oled import MockOledDriver, Ssd1306OledConfig, Ssd1306OledDriver
from dmc_ai_mobility.zenoh import keys
from dmc_ai_mobility.zenoh.pubsub import publish_json, subscribe_json
from dmc_ai_mobility.zenoh.session import ZenohOpenOptions, open_session

logger = logging.getLogger(__name__)


def _load_motor_trim(path: Path) -> float:
    try:
        if not path.exists():
            return 0.0
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data.get("trim") or 0.0)
    except Exception:
        return 0.0


def _lidar_front_distance(points: list[dict], *, window_deg: float, stat: str) -> Optional[tuple[float, int]]:
    half = max(float(window_deg), 0.0) / 2.0
    dists: list[float] = []
    for p in points:
        try:
            angle_rad = float(p.get("angle_rad"))
            dist = float(p.get("range_m"))
        except Exception:
            continue
        if dist <= 0.0:
            continue
        if abs(math.degrees(angle_rad)) <= half:
            dists.append(dist)
    if not dists:
        return None
    if str(stat).lower() == "min":
        return (min(dists), len(dists))
    return (sum(dists) / len(dists), len(dists))


def run_robot(config: RobotConfig, *, dry_run: bool, no_camera: bool, log_all_cmd: bool = False) -> int:
    robot_id = config.robot_id

    zenoh_cfg = ZenohOpenOptions(
        config_path=Path(config.zenoh.config_path) if config.zenoh.config_path else None
    )
    # Zenoh セッションを開き、以降は subscribe/publish をこの session 経由で行う。
    session = open_session(dry_run=dry_run, options=zenoh_cfg)

    # デフォルトは mock ドライバ（dry_run や初期化失敗時でもプロセスを起動できるようにする）。
    motor = MockMotorDriver()
    imu = MockImuDriver()
    oled = MockOledDriver()
    camera = MockCameraDriver()
    lidar = MockLidarDriver()
    lidar_enabled = bool(config.lidar.enable)

    if not dry_run:
        try:
            # モーターの左右差補正（任意）。存在しない場合は 0.0 として扱う。
            trim = _load_motor_trim(Path("configs/motor_config.json"))
            motor = PigpioMotorDriver(
                PigpioMotorConfig(pin_l=config.gpio.pin_l, pin_r=config.gpio.pin_r, trim=trim)
            )
        except Exception as e:
            logger.warning("motor driver unavailable; using mock (%s)", e)

        try:
            imu = Mpu9250ImuDriver(MpuImuConfig())
        except Exception as e:
            logger.warning("imu driver unavailable; using mock (%s)", e)

        if config.camera.enable and not no_camera:
            try:
                # V4L2/OpenCV からフレームを取得し、JPEG バイト列として取り出す。
                camera = OpenCVCameraDriver(
                    OpenCVCameraConfig(
                        device=config.camera.device, width=config.camera.width, height=config.camera.height
                    )
                )
            except Exception as e:
                logger.warning("camera driver unavailable; disabling camera (%s)", e)
                no_camera = True

        try:
            oled = Ssd1306OledDriver(
                Ssd1306OledConfig(
                    i2c_port=config.oled.i2c_port,
                    i2c_address=config.oled.i2c_address,
                    width=config.oled.width,
                    height=config.oled.height,
                )
            )
        except Exception as e:
            logger.warning("oled driver unavailable; using mock (%s)", e)

        if lidar_enabled:
            try:
                lidar = YdLidarDriver(
                    YdLidarConfig(
                        serial_port=config.lidar.port,
                        serial_baudrate=config.lidar.baudrate,
                    )
                )
            except Exception as e:
                logger.warning("lidar driver unavailable; disabling lidar (%s)", e)
                lidar_enabled = False

    stop_event = threading.Event()

    last_motor_cmd_ms: Optional[int] = None
    motor_deadman_ms = int(config.motor.deadman_ms)
    motor_active = False
    last_motor_log_ms: int = 0
    if dry_run:
        # Provide a no-input safety demonstration path: the deadman triggers after startup.
        last_motor_cmd_ms = monotonic_ms()
        motor_active = True

    def on_motor_cmd(data: dict) -> None:
        nonlocal last_motor_cmd_ms, motor_deadman_ms, motor_active, last_motor_log_ms
        try:
            # motor/cmd（JSON）を解釈して左右速度（m/s）を適用する。
            cmd = MotorCmd.from_dict(data)
        except Exception as e:
            logger.warning("invalid motor cmd: %s", e)
            return
        # 受信した指令をログ表示（ターミナルで確認しやすいように間引きあり）。
        # NOTE: 指令は高頻度になり得るため、ログが流れすぎないように上限を設ける。
        now = monotonic_ms()
        motor_log_max_hz = 10.0
        motor_log_min_interval_ms = int(1000.0 / motor_log_max_hz)
        if log_all_cmd or (now - last_motor_log_ms >= motor_log_min_interval_ms):
            logger.info(
                "motor cmd: v_l=%.3f v_r=%.3f unit=%s deadman_ms=%s seq=%s ts_ms=%s",
                cmd.v_l,
                cmd.v_r,
                cmd.unit,
                cmd.deadman_ms,
                cmd.seq,
                cmd.ts_ms,
            )
            last_motor_log_ms = now
        # deadman の ms は送信側から上書きできる（未指定なら config の値を維持）。
        motor_deadman_ms = int(cmd.deadman_ms or motor_deadman_ms)
        motor.set_velocity_mps(cmd.v_l, cmd.v_r)
        last_motor_cmd_ms = monotonic_ms()
        motor_active = True

    last_oled_update_ms: int = 0

    def on_oled_cmd(data: dict) -> None:
        nonlocal last_oled_update_ms
        try:
            # oled/cmd（JSON）を解釈して表示文字列を更新する。
            cmd = OledCmd.from_dict(data)
        except Exception as e:
            logger.warning("invalid oled cmd: %s", e)
            return
        if log_all_cmd:
            logger.info("oled cmd (recv): text=%s ts_ms=%s", cmd.text, cmd.ts_ms)
        now = monotonic_ms()
        min_interval_ms = int(1000.0 / max(config.oled.max_hz, 1.0))
        # OLED への更新頻度を上限で制限（画面更新の負荷/ちらつき抑制）。
        if now - last_oled_update_ms < min_interval_ms:
            return
        if not log_all_cmd:
            logger.info("oled cmd: text=%s ts_ms=%s", cmd.text, cmd.ts_ms)
        oled.show_text(cmd.text)
        last_oled_update_ms = now

    subs = [
        subscribe_json(session, keys.motor_cmd(robot_id), on_motor_cmd),
        subscribe_json(session, keys.oled_cmd(robot_id), on_oled_cmd),
    ]

    def imu_loop() -> None:
        # IMU を一定周期で読み取り、imu/state に JSON を publish する。
        sleeper = PeriodicSleeper(config.imu.publish_hz)
        key = keys.imu_state(robot_id)
        while not stop_event.is_set():
            state = imu.read()
            publish_json(session, key, state.to_dict())
            sleeper.sleep()

    imu_thread = threading.Thread(target=imu_loop, name="imu_loop", daemon=True)
    imu_thread.start()

    camera_thread: Optional[threading.Thread] = None
    if config.camera.enable and not no_camera:
        def camera_loop() -> None:
            # カメラ画像（JPEG バイト列）を一定 FPS で publish する。
            sleeper = PeriodicSleeper(config.camera.fps)
            key_img = keys.camera_image_jpeg(robot_id)
            key_meta = keys.camera_meta(robot_id)
            seq = 0
            while not stop_event.is_set():
                frame = camera.read_jpeg()
                if frame:
                    jpeg, w, h = frame
                    # 画像本体は `camera/image/jpeg` にそのまま bytes を publish（payload は JPEG）。
                    session.publish(key_img, jpeg)
                    # 画像メタ情報（サイズ/FPS/連番/時刻）を `camera/meta` に JSON で publish。
                    publish_json(
                        session,
                        key_meta,
                        {"width": w, "height": h, "fps": config.camera.fps, "seq": seq, "ts_ms": wall_clock_ms()},
                    )
                    seq += 1
                sleeper.sleep()

        camera_thread = threading.Thread(target=camera_loop, name="camera_loop", daemon=True)
        camera_thread.start()

    lidar_thread: Optional[threading.Thread] = None
    if lidar_enabled:
        def lidar_loop() -> None:
            sleeper = PeriodicSleeper(config.lidar.publish_hz)
            key_scan = keys.lidar_scan(robot_id)
            key_front = keys.lidar_front(robot_id)
            seq = 0
            while not stop_event.is_set():
                scan = lidar.read()
                if scan is not None:
                    points = [
                        {"angle_rad": p.angle_rad, "range_m": p.range_m, "intensity": p.intensity}
                        for p in scan.points
                    ]
                    publish_json(
                        session,
                        key_scan,
                        {"seq": seq, "ts_ms": scan.ts_ms, "points": points},
                    )
                    front = _lidar_front_distance(
                        points,
                        window_deg=config.lidar.front_window_deg,
                        stat=config.lidar.front_stat,
                    )
                    if front is not None:
                        distance_m, samples = front
                        publish_json(
                            session,
                            key_front,
                            {
                                "seq": seq,
                                "ts_ms": scan.ts_ms,
                                "window_deg": config.lidar.front_window_deg,
                                "stat": config.lidar.front_stat,
                                "distance_m": distance_m,
                                "samples": samples,
                            },
                        )
                    seq += 1
                sleeper.sleep()

        lidar_thread = threading.Thread(target=lidar_loop, name="lidar_loop", daemon=True)
        lidar_thread.start()

    logger.info("robot node started (robot_id=%s)", robot_id)

    try:
        while not stop_event.is_set():
            now = monotonic_ms()
            # deadman: 指令が途絶したら一定時間後に停止させる（安全対策）。
            if motor_active and last_motor_cmd_ms is not None and (now - last_motor_cmd_ms) > motor_deadman_ms:
                logger.warning("deadman timeout -> motor stop")
                motor.stop()
                motor_active = False
            stop_event.wait(0.05)
    except KeyboardInterrupt:
        logger.info("shutdown requested")
    finally:
        stop_event.set()
        try:
            for sub in subs:
                try:
                    sub.close()
                except Exception:
                    pass
        finally:
            try:
                motor.stop()
            except Exception:
                pass
            try:
                motor.close()
            except Exception:
                pass
            try:
                imu.close()
            except Exception:
                pass
            try:
                camera.close()
            except Exception:
                pass
            try:
                lidar.close()
            except Exception:
                pass
            try:
                oled.close()
            except Exception:
                pass
            try:
                session.close()
            except Exception:
                pass

    if imu_thread.is_alive():
        imu_thread.join(timeout=1.0)
    if camera_thread and camera_thread.is_alive():
        camera_thread.join(timeout=1.0)
    if lidar_thread and lidar_thread.is_alive():
        lidar_thread.join(timeout=1.0)

    return 0
