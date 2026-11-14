set -eu
cd /root/wzl/weak_coverage_camera_m_teacher
export PYTHONDONTWRITEBYTECODE=1
exec /root/pby/code/VSFusionDistill/.venv-gpu/bin/python -B -u tools/launch_weak_teacher_5090.py
