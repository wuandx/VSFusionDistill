set -eu
BASE=/root/wzl/weak_coverage_camera_m_teacher
test ! -e "$BASE/runs/weak_coverage_camera_m_teacher/remote-launch-status.json"
test ! -e "$BASE/runs/weak_coverage_camera_m_teacher/preflight"
cp /mnt/c/Users/Administrator/start_weak_teacher_5090_foreground.sh "$BASE/tools/"
sha256sum "$BASE/tools/start_weak_teacher_5090_foreground.sh"
