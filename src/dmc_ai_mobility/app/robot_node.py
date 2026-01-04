from __future__ import annotations

import json
import logging
import math
import threading
import time
from pathlib import Path
from typing import Optional

from dmc_ai_mobility.core.config import RobotConfig
from dmc_ai_mobility.core.oled_bitmap import mono1_buf_len
from dmc_ai_mobility.core.timing import PeriodicSleeper, monotonic_ms, wall_clock_ms
from dmc_ai_mobility.core.types import MotorCmd, OledCmd, OledModeCmd
from dmc_ai_mobility.app.oled_mode_manager import OledModeManager, OLED_MODE_DRIVE, OLED_MODE_SETTINGS
from dmc_ai_mobility.app.oled_settings_actions import OledSettingsActionRunner
from dmc_ai_mobility.drivers.camera_h264 import (
    LibcameraH264Config,
    LibcameraH264Driver,
    MockH264Driver,
)
from dmc_ai_mobility.drivers.camera_v4l2 import (
    CameraFrame,
    MockCameraDriver,
    OpenCVCameraConfig,
    OpenCVCameraDriver,
)
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


def run_robot(
    config: RobotConfig,
    *,
    dry_run: bool,
    no_camera: bool,
    log_all_cmd: bool = False,
    print_motor_pw: bool = False,
) -> int:
    robot_id = config.robot_id

    zenoh_cfg = ZenohOpenOptions(
        config_path=Path(config.zenoh.config_path) if config.zenoh.config_path else None
    )
    # Zenoh セッションを開き、以降は subscribe/publish をこの session 経由で行う。
    session = open_session(dry_run=dry_run, options=zenoh_cfg)

    # デフォルトは mock ドライバ（dry_run や初期化失敗時でもプロセスを起動できるようにする）。
    trim = 0.0
    if not dry_run:
        # モーターの左右差補正（任意）。存在しない場合は 0.0 として扱う。
        trim = _load_motor_trim(Path("configs/motor_config.json"))
    motor_cfg = PigpioMotorConfig(
        pin_l=config.gpio.pin_l,
        pin_r=config.gpio.pin_r,
        trim=trim,
        deadband_pw=int(config.motor.deadband_pw),
        print_pulsewidth=print_motor_pw,
    )
    motor = MockMotorDriver(motor_cfg)
    imu = MockImuDriver()
    oled = MockOledDriver()
    camera = MockCameraDriver(width=config.camera.width, height=config.camera.height)
    h264_driver: Optional[LibcameraH264Driver | MockH264Driver] = None
    lidar = MockLidarDriver()
    lidar_enabled = bool(config.lidar.enable)

    if dry_run and config.camera_h264.enable:
        h264_driver = MockH264Driver(
            fps=config.camera_h264.fps,
            chunk_bytes=config.camera_h264.chunk_bytes,
        )

    if not dry_run:
        try:
            motor = PigpioMotorDriver(motor_cfg)
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
                        device=config.camera.device,
                        width=config.camera.width,
                        height=config.camera.height,
                        auto_trim=config.camera.auto_trim,
                        buffer_size=config.camera.buffer_size,
                        jpeg_quality=config.camera.jpeg_quality,
                    )
                )
            except Exception as e:
                logger.warning("camera driver unavailable; disabling camera (%s)", e)
                no_camera = True

        if config.camera_h264.enable:
            try:
                h264_driver = LibcameraH264Driver(
                    LibcameraH264Config(
                        width=config.camera_h264.width,
                        height=config.camera_h264.height,
                        fps=config.camera_h264.fps,
                        bitrate=config.camera_h264.bitrate,
                        chunk_bytes=config.camera_h264.chunk_bytes,
                    )
                )
            except Exception as e:
                logger.warning("camera h264 driver unavailable; disabling h264 (%s)", e)
                h264_driver = None

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

    last_motor_cmd: Optional[MotorCmd] = None
    last_motor_cmd_ms: Optional[int] = None
    motor_deadman_ms = int(config.motor.deadman_ms)
    motor_active = False
    last_motor_log_ms: int = 0
    if dry_run:
        # Provide a no-input safety demonstration path: the deadman triggers after startup.
        last_motor_cmd_ms = monotonic_ms()
        motor_active = True

    def on_motor_cmd(data: dict) -> None:
        nonlocal last_motor_cmd, last_motor_cmd_ms, motor_deadman_ms, motor_active, last_motor_log_ms
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
        last_motor_cmd = cmd
        last_motor_cmd_ms = monotonic_ms()
        motor_active = True

    oled_override_lock = threading.Lock()
    oled_override_until_ms: int = 0
    oled_override_kind: Optional[str] = None  # "text" | "mono1"
    oled_override_text: str = ""
    oled_override_mono1: bytes = b""
    oled_override_ms = int(max(float(config.oled.override_s), 0.0) * 1000.0)
    def on_oled_cmd(data: dict) -> None:
        nonlocal oled_override_until_ms, oled_override_kind, oled_override_text, oled_override_mono1
        try:
            cmd = OledCmd.from_dict(data)
        except Exception as e:
            logger.warning("invalid oled cmd: %s", e)
            return
        if log_all_cmd:
            logger.info("oled cmd (recv): text=%s ts_ms=%s", cmd.text, cmd.ts_ms)
        with oled_override_lock:
            oled_override_kind = "text"
            oled_override_text = cmd.text
            oled_override_mono1 = b""
            oled_override_until_ms = monotonic_ms() + oled_override_ms

    oled_width = int(config.oled.width)
    oled_height = int(config.oled.height)
    oled_expected_len = mono1_buf_len(oled_width, oled_height)
    oled_manager = OledModeManager(oled=oled, config=config, robot_id=robot_id, logger=logger)
    settings_actions = OledSettingsActionRunner(config=config, logger=logger, dry_run=dry_run)
    last_non_settings_mode = oled_manager.get_mode()

    def on_oled_image_mono1(payload: bytes) -> None:
        nonlocal oled_override_until_ms, oled_override_kind, oled_override_text, oled_override_mono1
        if log_all_cmd:
            logger.info("oled image/mono1 (recv): %d bytes", len(payload))
        if len(payload) != oled_expected_len:
            logger.warning(
                "invalid oled image/mono1 payload size: got=%d expected=%d (%sx%s)",
                len(payload),
                oled_expected_len,
                oled_width,
                oled_height,
            )
            return
        with oled_override_lock:
            oled_override_kind = "mono1"
            oled_override_mono1 = bytes(payload)
            oled_override_text = ""
            oled_override_until_ms = monotonic_ms() + oled_override_ms

    def on_oled_mode_cmd(data: dict) -> None:
        nonlocal last_non_settings_mode
        try:
            cmd = OledModeCmd.from_dict(data)
        except Exception as e:
            logger.warning("invalid oled mode cmd: %s", e)
            return
        if log_all_cmd:
            logger.info(
                "oled mode (recv): mode=%s settings_index=%s ts_ms=%s",
                cmd.mode,
                cmd.settings_index,
                cmd.ts_ms,
            )
        mode = str(cmd.mode or "").lower()
        if oled_manager.has_mode(mode) and mode != OLED_MODE_SETTINGS:
            last_non_settings_mode = mode
        oled_manager.set_mode(mode, settings_index=cmd.settings_index)

    subs = [
        subscribe_json(session, keys.motor_cmd(robot_id), on_motor_cmd),
        subscribe_json(session, keys.oled_cmd(robot_id), on_oled_cmd),
        session.subscribe(keys.oled_image_mono1(robot_id), on_oled_image_mono1),
        subscribe_json(session, keys.oled_mode(robot_id), on_oled_mode_cmd),
    ]

    def oled_loop() -> None:
        nonlocal oled_override_until_ms, oled_override_kind, oled_override_text, oled_override_mono1
        # OLED 表示は 1 つのループに集約し、優先順位で表示内容を決める。
        # 1) Zenoh から来た override（text / mono1）
        # 2) base UI mode（manager が mode switch / welcome を処理）
        hz = max(float(config.oled.max_hz), 1.0)
        sleeper = PeriodicSleeper(hz)
        while not stop_event.is_set():
            now = monotonic_ms()

            kind: Optional[str]
            text: str
            mono1: bytes
            until_ms: int
            with oled_override_lock:
                kind = oled_override_kind
                text = oled_override_text
                mono1 = oled_override_mono1
                until_ms = oled_override_until_ms

            if kind and now < until_ms:
                try:
                    if kind == "mono1":
                        oled.show_mono1(mono1)
                    else:
                        oled.show_text(text)
                except Exception as e:
                    logger.warning("oled override render failed: %s", e)
                sleeper.sleep()
                continue

            if kind and now >= until_ms:
                with oled_override_lock:
                    if oled_override_kind == kind and oled_override_until_ms == until_ms:
                        oled_override_kind = None
                        oled_override_text = ""
                        oled_override_mono1 = b""
                        oled_override_until_ms = 0

            try:
                oled_manager.render(
                    now,
                    motor_cmd=last_motor_cmd,
                    motor_cmd_ms=last_motor_cmd_ms,
                    motor_deadman_ms=motor_deadman_ms,
                )
            except Exception as e:
                logger.warning("oled base render failed: %s", e)

            sleeper.sleep()

    oled_thread = threading.Thread(target=oled_loop, name="oled_loop", daemon=True)
    oled_thread.start()

    button_thread: Optional[threading.Thread] = None

    def button_loop() -> None:
        nonlocal last_non_settings_mode
        if dry_run:
            return
        try:
            import pigpio  # type: ignore
        except Exception as e:
            logger.warning("pigpio unavailable; SW input disabled (%s)", e)
            return
        pi = pigpio.pi()
        if not pi.connected:
            logger.warning("pigpio daemon not connected; SW input disabled")
            return

        sw1 = int(config.gpio.sw1)
        sw2 = int(config.gpio.sw2)
        for sw in (sw1, sw2):
            pi.set_mode(sw, pigpio.INPUT)
            pi.set_pull_up_down(sw, pigpio.PUD_UP)

        debounce_ms = 50
        long_press_ms = 600
        poll_s = 0.02

        sw1_state = pi.read(sw1)
        sw2_state = pi.read(sw2)
        sw1_last_change = monotonic_ms()
        sw2_last_change = monotonic_ms()
        sw1_press_start: Optional[int] = None
        sw2_press_start: Optional[int] = None

        def handle_sw1_short() -> None:
            mode = oled_manager.get_mode()
            if mode == OLED_MODE_SETTINGS:
                oled_manager.step_settings_index(1)
            else:
                oled_manager.cycle_mode(1)

        def handle_sw1_long() -> None:
            mode = oled_manager.get_mode()
            if mode == OLED_MODE_SETTINGS:
                oled_manager.step_settings_index(-1)
            else:
                oled_manager.cycle_mode(-1)

        def handle_sw2_short() -> None:
            nonlocal last_non_settings_mode
            mode = oled_manager.get_mode()
            if mode == OLED_MODE_SETTINGS:
                item = oled_manager.get_settings_item()
                if item:
                    handled = settings_actions.trigger_item(item)
                    if not handled:
                        logger.info("settings select: %s (no action)", item)
                return
            last_non_settings_mode = mode
            oled_manager.set_mode(OLED_MODE_SETTINGS)

        def handle_sw2_long() -> None:
            nonlocal last_non_settings_mode
            target = last_non_settings_mode or oled_manager.get_mode()
            if target == OLED_MODE_SETTINGS:
                target = OLED_MODE_DRIVE
            oled_manager.set_mode(target)

        try:
            while not stop_event.is_set():
                now = monotonic_ms()
                s1 = pi.read(sw1)
                if s1 != sw1_state and (now - sw1_last_change) >= debounce_ms:
                    sw1_state = s1
                    sw1_last_change = now
                    if s1 == 0:
                        sw1_press_start = now
                    else:
                        if sw1_press_start is not None:
                            duration = now - sw1_press_start
                            sw1_press_start = None
                            if duration >= long_press_ms:
                                handle_sw1_long()
                            else:
                                handle_sw1_short()

                s2 = pi.read(sw2)
                if s2 != sw2_state and (now - sw2_last_change) >= debounce_ms:
                    sw2_state = s2
                    sw2_last_change = now
                    if s2 == 0:
                        sw2_press_start = now
                    else:
                        if sw2_press_start is not None:
                            duration = now - sw2_press_start
                            sw2_press_start = None
                            if duration >= long_press_ms:
                                handle_sw2_long()
                            else:
                                handle_sw2_short()

                time.sleep(poll_s)
        finally:
            try:
                pi.stop()
            except Exception:
                pass

    if not dry_run:
        button_thread = threading.Thread(target=button_loop, name="button_loop", daemon=True)
        button_thread.start()

    motor_telemetry_thread: Optional[threading.Thread] = None
    motor_telemetry_hz = float(config.motor.telemetry_hz)
    if motor_telemetry_hz > 0.0:
        def motor_telemetry_loop() -> None:
            sleeper = PeriodicSleeper(motor_telemetry_hz)
            key = keys.motor_telemetry(robot_id)
            while not stop_event.is_set():
                pulsewidth = motor.get_last_pulsewidths()
                cmd = last_motor_cmd
                payload = {
                    "pw_l": pulsewidth.pw_l,
                    "pw_r": pulsewidth.pw_r,
                    "pw_l_raw": pulsewidth.pw_l_raw,
                    "pw_r_raw": pulsewidth.pw_r_raw,
                    "ts_ms": wall_clock_ms(),
                    "cmd_v_l": cmd.v_l if cmd else None,
                    "cmd_v_r": cmd.v_r if cmd else None,
                    "cmd_unit": cmd.unit if cmd else None,
                    "cmd_deadman_ms": cmd.deadman_ms if cmd else None,
                    "cmd_seq": cmd.seq if cmd else None,
                    "cmd_ts_ms": cmd.ts_ms if cmd else None,
                }
                publish_json(session, key, payload)
                sleeper.sleep()

        motor_telemetry_thread = threading.Thread(
            target=motor_telemetry_loop,
            name="motor_telemetry_loop",
            daemon=True,
        )
        motor_telemetry_thread.start()

    def imu_loop() -> None:
        # IMU（ジャイロ/加速度）を一定周期で読み取り、imu/state に JSON を publish する。
        sleeper = PeriodicSleeper(config.imu.publish_hz)
        key = keys.imu_state(robot_id)
        while not stop_event.is_set():
            state = imu.read()
            publish_json(session, key, state.to_dict())
            sleeper.sleep()

    imu_thread = threading.Thread(target=imu_loop, name="imu_loop", daemon=True)
    imu_thread.start()

    camera_thread: Optional[threading.Thread] = None
    camera_capture_thread: Optional[threading.Thread] = None
    if config.camera.enable and not no_camera:
        if config.camera.latest_only:
            latest_lock = threading.Lock()
            latest_frame: Optional[tuple[int, CameraFrame]] = None
            capture_seq = 0

            def capture_loop() -> None:
                # 最新フレームのみ保持する（溜まりを防ぐ）
                nonlocal latest_frame, capture_seq
                sleeper = PeriodicSleeper(config.camera.fps)
                while not stop_event.is_set():
                    frame = camera.read_jpeg()
                    if frame:
                        with latest_lock:
                            latest_frame = (capture_seq, frame)
                        capture_seq += 1
                    sleeper.sleep()

            def publish_loop() -> None:
                # カメラ画像（JPEG バイト列）を一定 FPS で publish する。
                sleeper = PeriodicSleeper(config.camera.fps)
                key_img = keys.camera_image_jpeg(robot_id)
                key_meta = keys.camera_meta(robot_id)
                last_published_seq = -1
                while not stop_event.is_set():
                    with latest_lock:
                        current = latest_frame
                    if current:
                        seq, frame = current
                        if seq != last_published_seq:
                            # 画像本体は `camera/image/jpeg` にそのまま bytes を publish（payload は JPEG）。
                            session.publish(key_img, frame.jpeg)
                            # publish 実行時刻を取得（パイプライン遅延の計測用）
                            publish_wall_ms = wall_clock_ms()
                            publish_mono_ms = monotonic_ms()
                            pipeline_ms = max(0, publish_mono_ms - frame.capture_mono_ms)
                            # 画像メタ情報（サイズ/FPS/連番/時刻）を `camera/meta` に JSON で publish。
                            publish_json(
                                session,
                                key_meta,
                                {
                                    "width": frame.width,
                                    "height": frame.height,
                                    "fps": config.camera.fps,
                                    "seq": seq,
                                    "ts_ms": publish_wall_ms,
                                    "capture_ts_ms": frame.capture_wall_ms,
                                    "publish_ts_ms": publish_wall_ms,
                                    "pipeline_ms": pipeline_ms,
                                    "capture_mono_ms": frame.capture_mono_ms,
                                    "publish_mono_ms": publish_mono_ms,
                                    "capture_start_mono_ms": frame.capture_start_mono_ms,
                                    "capture_end_mono_ms": frame.capture_end_mono_ms,
                                    "read_ms": frame.read_ms,
                                },
                            )
                            last_published_seq = seq
                    sleeper.sleep()

            camera_capture_thread = threading.Thread(
                target=capture_loop, name="camera_capture_loop", daemon=True
            )
            camera_thread = threading.Thread(
                target=publish_loop, name="camera_publish_loop", daemon=True
            )
            camera_capture_thread.start()
            camera_thread.start()
        else:
            def camera_loop() -> None:
                # カメラ画像（JPEG バイト列）を一定 FPS で publish する。
                sleeper = PeriodicSleeper(config.camera.fps)
                key_img = keys.camera_image_jpeg(robot_id)
                key_meta = keys.camera_meta(robot_id)
                seq = 0
                while not stop_event.is_set():
                    frame = camera.read_jpeg()
                    if frame:
                        # 画像本体は `camera/image/jpeg` にそのまま bytes を publish（payload は JPEG）。
                        session.publish(key_img, frame.jpeg)
                        # publish 実行時刻を取得（パイプライン遅延の計測用）
                        publish_wall_ms = wall_clock_ms()
                        publish_mono_ms = monotonic_ms()
                        pipeline_ms = max(0, publish_mono_ms - frame.capture_mono_ms)
                        # 画像メタ情報（サイズ/FPS/連番/時刻）を `camera/meta` に JSON で publish。
                        publish_json(
                            session,
                            key_meta,
                            {
                                "width": frame.width,
                                "height": frame.height,
                                "fps": config.camera.fps,
                                "seq": seq,
                                "ts_ms": publish_wall_ms,
                                "capture_ts_ms": frame.capture_wall_ms,
                                "publish_ts_ms": publish_wall_ms,
                                "pipeline_ms": pipeline_ms,
                                "capture_mono_ms": frame.capture_mono_ms,
                                "publish_mono_ms": publish_mono_ms,
                                "capture_start_mono_ms": frame.capture_start_mono_ms,
                                "capture_end_mono_ms": frame.capture_end_mono_ms,
                                "read_ms": frame.read_ms,
                            },
                        )
                        seq += 1
                    sleeper.sleep()

            camera_thread = threading.Thread(target=camera_loop, name="camera_loop", daemon=True)
            camera_thread.start()

    h264_thread: Optional[threading.Thread] = None
    if h264_driver is not None:
        def h264_loop() -> None:
            logger.info(
                "camera h264 started (%sx%s @ %.1ffps, bitrate=%s)",
                config.camera_h264.width,
                config.camera_h264.height,
                config.camera_h264.fps,
                config.camera_h264.bitrate,
            )
            key_video = keys.camera_video_h264(robot_id)
            key_meta = keys.camera_video_h264_meta(robot_id)
            seq = 0
            while not stop_event.is_set():
                chunk = h264_driver.read_chunk()
                if chunk is None:
                    break
                if not chunk:
                    continue
                session.publish(key_video, chunk)
                publish_json(
                    session,
                    key_meta,
                    {
                        "codec": "h264",
                        "width": config.camera_h264.width,
                        "height": config.camera_h264.height,
                        "fps": config.camera_h264.fps,
                        "bitrate": config.camera_h264.bitrate,
                        "seq": seq,
                        "ts_ms": wall_clock_ms(),
                        "bytes": len(chunk),
                    },
                )
                seq += 1

        h264_thread = threading.Thread(target=h264_loop, name="camera_h264_loop", daemon=True)
        h264_thread.start()

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
                if h264_driver is not None:
                    h264_driver.close()
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
    if motor_telemetry_thread and motor_telemetry_thread.is_alive():
        motor_telemetry_thread.join(timeout=1.0)
    if oled_thread.is_alive():
        oled_thread.join(timeout=1.0)
    if camera_thread and camera_thread.is_alive():
        camera_thread.join(timeout=1.0)
    if camera_capture_thread and camera_capture_thread.is_alive():
        camera_capture_thread.join(timeout=1.0)
    if h264_thread and h264_thread.is_alive():
        h264_thread.join(timeout=1.0)
    if lidar_thread and lidar_thread.is_alive():
        lidar_thread.join(timeout=1.0)
    if button_thread and button_thread.is_alive():
        button_thread.join(timeout=1.0)

    return 0
