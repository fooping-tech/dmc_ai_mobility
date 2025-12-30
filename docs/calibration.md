# キャリブレーション（モーター / IMU）

このプロジェクトでは、実機の個体差を吸収するためにいくつかの補正値（JSON）を用意しています。

- モーター補正: `configs/motor_config.json`（`trim`）
- IMU 補正: `configs/imu_config.json`（`gx_off/gy_off/gz_off` など）

## モーター（`trim`）のキャリブレーション

### 概要
左右のモーター出力差により「まっすぐ走らない」場合に、`trim` で左右の速度に係数を掛けて補正します。

実行時は `src/dmc_ai_mobility/app/robot_node.py` が `configs/motor_config.json` の `trim` を読み込み、速度指令に反映します。

### 手順（簡易）
1. 安全のため、車体を浮かせる/十分なスペースを確保する（転倒・暴走に注意）。
2. `pigpio` デーモンを起動しておく（環境により `sudo systemctl start pigpiod` など）。
3. キャリブレーションスクリプトを実行:

   ```bash
   PYTHONPATH=src python3 -m dmc_ai_mobility.calibration.motor
   ```

4. 走行が左右どちらに寄るかを見ながら、スイッチ入力で `TRIM` を微調整し、保存して終了します。
5. `configs/motor_config.json` に保存されます（既存ファイルは上書き）。

### 補足
- GPIO ピンやスイッチ割り当てはキャリブレーションスクリプト側の設定に依存します（`src/dmc_ai_mobility/calibration/motor.py`）。
- `trim` は「0.0 が補正なし」です。大きくし過ぎると逆に曲がるので少しずつ調整してください。

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
