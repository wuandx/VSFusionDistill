set -eu
BASE=/root/wzl/weak_coverage_camera_m_teacher
ls -la "$BASE/runs/weak_coverage_camera_m_teacher"
cat "$BASE/runs/weak_coverage_camera_m_teacher/service.log"
ps -p 1 -o pid,args
cat /etc/wsl.conf
command -v setsid
ls -l /run/dbus/system_bus_socket /run/systemd/private 2>/dev/null || true
