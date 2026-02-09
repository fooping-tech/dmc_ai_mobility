# 実機当日チェックリスト（10分）

## 1. 起動
```bash
export ROBOT_ID=rasp-zero-01
export ZENOH_CONFIG=/work/../zenoh_remote.json5
/work/bringup_realrobot_localization.sh /work/maps/map.yaml
```

## 2. Preflight
```bash
/work/preflight_check.sh
```
- すべて `[ok]` になること

## 3. 近距離goalで疎通確認
```bash
/work/send_goal.sh 0.3 0.0 0.0
```
- rejectされないこと

## 4. 本命goal
```bash
/work/send_goal.sh 1.0 0.0 0.0
```

## 5. 問題時
- `RUNBOOK_REALROBOT_NAV2.md` を参照
- ログ保存:
  - `/tmp/dmc_nav2_realrobot_loc/*.log`
