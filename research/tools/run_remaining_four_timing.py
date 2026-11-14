from pathlib import Path
import sys
sys.dont_write_bytecode=True
import check_camera_aris_continuous_timing as timing
timing.RECS=['2023-09-21_'+s for s in ('100927','101131','120653','120912')]
timing.OUT=timing.ROOT/'DataSet/sonar_four_recording_timing'
if __name__=='__main__': timing.main()
