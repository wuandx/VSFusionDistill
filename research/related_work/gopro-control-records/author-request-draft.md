# Draft — not sent

Suggested destination: the maintainers of [dfki-ric/uxo-dataset2024](https://github.com/dfki-ric/uxo-dataset2024). The existing [issue #5](https://github.com/dfki-ric/uxo-dataset2024/issues/5) already asks related imaging-model questions; this draft focuses on the original records and independent AprilTag controls. Do not post a duplicate automatically.

Subject: Original GoPro calibration records and AprilTag cube dimensions for UXO Dataset 2024

Hello,

We are auditing the released camera–sonar projection geometry before producing sonar bounding boxes. We have reproduced the published export-time indexing and gantry interpolation for a small development subset, but have not yet established the physical camera model, synchronization accuracy, or target-mesh registration. We are preserving the published transforms and avoiding per-frame model adjustments.

Could you help identify the original records for these six recordings?

| Recording | Released GoPro clip basename |
|---|---|
| 2023-09-20_171105 | 20230920_GX010010_01 |
| 2023-09-20_173329 | 20230920_GX020009_01 |
| 2023-09-21_100927 | 20230921_GX010012_01 |
| 2023-09-21_101131 | 20230921_GX010012_02 |
| 2023-09-21_120653 | 20230921_GX010014_01 |
| 2023-09-21_120912 | 20230921_GX010014_02 |

1. **Capture settings and original metadata.** Which camera model, digital lens mode and stabilization settings were used? Were they constant across these clips? A recording-to-settings table or the metadata from the original uncut GoPro files would be sufficient. The released UHD clips are 5312×2988 at 30000/1001 fps and retain a timecode track, but no `gpmd` telemetry track, so we cannot verify the settings from the released containers.

2. **The calibration that applies to these recordings.** Could you share the calibration script or an exact projection/undistortion example, including coefficient order, calibration image dimensions and any cropping or stabilization assumptions? Were the calibration images taken underwater, with the same camera housing/port and settings as the dataset? Calibration observations, board dimensions and reprojection residuals would let us verify the result independently. We found four current parameter files and an older README describing a wide-mode fisheye calibration, but cannot establish which applies to these recordings.

3. **AprilTag cube geometry.** We detected `tag36h11` IDs 20, 21 and 141 on the cube in existing frames. Could you provide the measured tag side length used by the pose estimator, the cube dimensions, and the ID-to-face transforms/corner order? In particular, `demo/camera_tilt.ipynb` uses `tag_size=0.30` in one section and `0.247` for tag 20 later. Do these refer to different physical extents, such as the cube edge versus the tag's outer black border? If the cube was repositioned between recordings or target changes, could you identify those groups? A measured drawing, CAD file or corner-coordinate table would be helpful. World coordinates are useful if available, but the face geometry and within-recording stationarity alone would already support relative-motion checks once the camera model is fixed.

4. **Synchronization and pose validation records.** Are the original camera/ARIS/gantry timing observations, any drift estimates, and the PTU angle/axis conventions or independent validation logs available? We can reproduce the exported numbers, but this does not independently validate acquisition-time synchronization. We would like to check a single constant offset per recording on one motion segment and validate it on a separate segment.

If the raw files cannot be shared, an explicit description of what was measured, what was assumed, and which files correspond to these recordings would still be valuable. Please also let us know if these records are no longer available; we will retain the relevant uncertainties rather than infer a new calibration from the same target mesh we want to validate.

Thank you.
