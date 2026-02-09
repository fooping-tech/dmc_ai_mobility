#!/usr/bin/env bash
set -euo pipefail

# Offline Nav2 planner benchmark (no real robot required)
# - Runs ComputePathToPose on custom map for several planner/costmap variants
# - Outputs CSV + markdown summary under /work

cd /work
set +u
source /opt/ros/humble/setup.bash
set -u

MAP_PATH=${MAP_PATH:-/work/../nav2_custom_map/custom_map.yaml}
BASE_PARAMS=${BASE_PARAMS:-/work/src/dmc_nav_bridge/config/nav2_params.yaml}
OUT_CSV=${OUT_CSV:-/work/nav2_param_benchmark.csv}
OUT_MD=${OUT_MD:-/work/nav2_param_benchmark.md}

START_X=${START_X:--4.0}
START_Y=${START_Y:-0.0}
GOAL_X=${GOAL_X:-4.0}
GOAL_Y=${GOAL_Y:--2.0}

tmpdir=$(mktemp -d)
cleanup() {
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
  rm -rf "$tmpdir"
}
trap cleanup EXIT INT TERM

mk_params() {
  local name="$1" tol="$2" astar="$3" infl="$4"
  local out="$tmpdir/${name}.yaml"
  cp "$BASE_PARAMS" "$out"
  sed -i "s/tolerance: .*/tolerance: ${tol}/" "$out"
  sed -i "s/use_astar: .*/use_astar: ${astar}/" "$out"
  sed -i "s/inflation_radius: .*/inflation_radius: ${infl}/g" "$out"
  echo "$out"
}

run_case() {
  local name="$1" params="$2"
  local log="$tmpdir/${name}.log"

  ros2 launch nav2_bringup bringup_launch.py \
    slam:=False map:="$MAP_PATH" use_sim_time:=False autostart:=True \
    params_file:="$params" >"$log" 2>&1 &
  local navpid=$!

  ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map odom >/dev/null 2>&1 &
  local t1=$!
  ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 odom base_link >/dev/null 2>&1 &
  local t2=$!

  sleep 22

  CASE_NAME="$name" SX="$START_X" SY="$START_Y" GX="$GOAL_X" GY="$GOAL_Y" \
  python3 - <<'PY'
import csv, os, math, rclpy
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import ComputePathToPose

case = os.environ['CASE_NAME']
sx,sy,gx,gy = [float(os.environ[k]) for k in ('SX','SY','GX','GY')]

rclpy.init()
node=rclpy.create_node(f'bench_{case}')
ac=ActionClient(node, ComputePathToPose, '/compute_path_to_pose')
ready=ac.wait_for_server(timeout_sec=12.0)
accepted=False; status=-1; nposes=0; length_m=0.0
if ready:
    goal=ComputePathToPose.Goal()
    st=PoseStamped(); st.header.frame_id='map'; st.pose.position.x=sx; st.pose.position.y=sy; st.pose.orientation.w=1.0
    gl=PoseStamped(); gl.header.frame_id='map'; gl.pose.position.x=gx; gl.pose.position.y=gy; gl.pose.orientation.w=1.0
    goal.start=st; goal.goal=gl; goal.use_start=True
    sf=ac.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, sf, timeout_sec=10.0)
    gh=sf.result()
    accepted=bool(gh and gh.accepted)
    if accepted:
      rf=gh.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=15.0)
      rr=rf.result()
      if rr:
        status=rr.status
        pts=[(p.pose.position.x,p.pose.position.y) for p in rr.result.path.poses]
        nposes=len(pts)
        for i in range(1,len(pts)):
          dx=pts[i][0]-pts[i-1][0]; dy=pts[i][1]-pts[i-1][1]
          length_m += math.hypot(dx,dy)

with open('/tmp/nav2_bench_row.csv','a',newline='') as f:
    w=csv.writer(f)
    w.writerow([case, int(ready), int(accepted), status, nposes, round(length_m,3)])

node.destroy_node(); rclpy.shutdown()
PY

  kill "$t2" "$t1" "$navpid" >/dev/null 2>&1 || true
  sleep 2
}

: > /tmp/nav2_bench_row.csv

p1=$(mk_params baseline 0.5 false 0.25)
p2=$(mk_params astar 0.5 true 0.25)
p3=$(mk_params tolerant 1.0 false 0.25)
p4=$(mk_params wide_inflation 0.5 false 0.40)

run_case baseline "$p1"
run_case astar "$p2"
run_case tolerant "$p3"
run_case wide_inflation "$p4"

{
  echo "case,server_ready,accepted,status,nposes,path_length_m"
  cat /tmp/nav2_bench_row.csv
} > "$OUT_CSV"

python3 - <<'PY'
import csv, os
csv_path=os.environ.get('OUT_CSV','/work/nav2_param_benchmark.csv')
md_path=os.environ.get('OUT_MD','/work/nav2_param_benchmark.md')
rows=list(csv.DictReader(open(csv_path)))
with open(md_path,'w') as f:
    f.write('# Nav2 parameter benchmark (offline)\n\n')
    f.write('| case | accepted | status | nposes | path_length_m |\n')
    f.write('|---|---:|---:|---:|---:|\n')
    for r in rows:
        f.write(f"| {r['case']} | {r['accepted']} | {r['status']} | {r['nposes']} | {r['path_length_m']} |\n")
print(md_path)
PY

echo "[done] $OUT_CSV"
echo "[done] $OUT_MD"
