set -eu
BASE=/root/wzl/weak_coverage_camera_m_teacher
date -Iseconds
cat "$BASE/runs/weak_coverage_camera_m_teacher/remote-launch-status.json" 2>/dev/null || true
for mode in preflight train; do
  test ! -f "$BASE/runs/weak_coverage_camera_m_teacher/$mode/status.json" || /root/pby/code/VSFusionDistill/.venv-gpu/bin/python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps({k:d.get(k) for k in ["status","gpu","mode","error","checks"]}))' "$BASE/runs/weak_coverage_camera_m_teacher/$mode/status.json"
  tail -n 4 "$BASE/runs/weak_coverage_camera_m_teacher/$mode.log" 2>/dev/null || true
done
tail -n 6 "$BASE/runs/weak_coverage_camera_m_teacher/service.log" 2>/dev/null || true
ps -eo pid,ppid,args | grep -E 'launch_weak_teacher_5090|run_weak_coverage_camera_teacher' | grep -v grep || true
nvidia-smi --query-gpu=name,memory.used,utilization.gpu --format=csv,noheader
