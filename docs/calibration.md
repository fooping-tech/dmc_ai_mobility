# キャリブレーション（モーター / IMU）

このプロジェクトでは、実機の個体差を吸収するためにいくつかの補正値（JSON）を用意しています。

- モーター補正: `configs/motor_config.json`（`v_start` と `trim_points`）
- IMU 補正: `configs/imu_config.json`（`gx_off/gy_off/gz_off` など）

## モーター（`v_start` + `trim_points`）のキャリブレーション

### 概要
左右のモーター出力差により「まっすぐ走らない」場合に、速度域ごとの `trim` を使って左右の速度に係数を掛けて補正します。あわせて、回転が始まる最小速度 `v_start` を測定して保存します。

実行時は `src/dmc_ai_mobility/app/robot_node.py` / `src/dmc_ai_mobility/drivers/motor.py` が `configs/motor_config.json` の `v_start` と `trim_points` を読み込み、速度指令に反映します。

### 手順（簡易）
1. 安全のため、車体を浮かせる/十分なスペースを確保する（転倒・暴走に注意）。
2. `pigpio` デーモンを起動しておく（環境により `sudo systemctl start pigpiod` など）。
3. キャリブレーションスクリプトを実行:

   ```bash
   PYTHONPATH=src python3 -m dmc_ai_mobility.calibration.motor
   ```

4. 走行が左右どちらに寄るかを見ながら、スイッチ入力で `v_start` と各速度域の `trim` を微調整し、保存して終了します。
5. `configs/motor_config.json` に保存されます（既存ファイルは上書き）。

### 補足
- GPIO ピンやスイッチ割り当ては `config.toml` の `[gpio]` を読み込み、未設定時はスクリプト側のデフォルトにフォールバックします（`src/dmc_ai_mobility/calibration/motor.py`）。
- `trim` は「0.0 が補正なし」です。大きくし過ぎると逆に曲がるので少しずつ調整してください。
- `trim` が正のときは「左モーターが強い」想定なので、左を弱めて右を強める方向に補正します。
- `trim_points` は速度（m/s）に対して補間され、近い速度域の補正が適用されます。

### スイッチ操作
- `SW1` 短押し: +（現在モードの値を増やす）
- `SW2` 短押し: -（現在モードの値を減らす）
- `SW1+SW2` 短押し: モード切替（`START_V` → `LOW_TRIM` → `MID_TRIM` → `HIGH_TRIM`）
- `SW1+SW2` 長押し（1.2s 以上）: 保存して終了

### 設定フォーマット
`configs/motor_config.json` は次の形で保存されます。

```json
{
  "v_start": 0.10,
  "trim_points": [
    {"label": "low", "v": 0.15, "trim": 0.00},
    {"label": "mid", "v": 0.30, "trim": 0.00},
    {"label": "high", "v": 0.50, "trim": 0.00}
  ]
}
```

### 互換性
旧形式の `trim` 単体（`{"trim": 0.00}`）も読み込めますが、最新の推奨は `v_start` + `trim_points` です。

## IMU（ジャイロ）オフセットのキャリブレーション

### 概要
静止状態でもジャイロにバイアス（オフセット）が乗ることがあります。静止状態の平均値を `*_off` として保存し、読み出し側で差し引く用途を想定しています。

### 手順（簡易）
1. ロボットを水平で動かない場所に置き、完全に静止させます。
2. キャリブレーションスクリプトを実行:

   ```bash
   PYTHONPATH=src python3 -m dmc_ai_mobility.calibration.imu
   ```

3. `configs/imu_config.json` に保存されます（既存ファイルは上書き）。

### 補足
`src/dmc_ai_mobility/drivers/imu.py` は `configs/imu_config.json` の `gx_off/gy_off/gz_off` を読み込み、ジャイロ値から差し引きます。
