import pandas as pd
import numpy as np
import os
from scipy.spatial.transform import Rotation as R

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D 
%matplotlib ipympl

from common.transforms import get_tf_manager

tm = get_tf_manager()

from common.config import get_config
config = get_config()

ROOT= '../' + config['aris_extract']
DATASET = '2023-09-20_171105'
FILENAME = 'ar3.csv'

df_ar3 = pd.read_csv(os.path.join(ROOT, DATASET, FILENAME))
df_ar3

from pytransform3d.plot_utils import make_3d_axis
import pytransform3d.transformations as pytr
from pytransform3d import visualizer as pv

ROOT_MESH = os.path.join('..', '..', '3d_models')
SCALING=20

fig = pv.figure()
fig.plot_mesh(filename=os.path.join(ROOT_MESH, "100lbs_aircraft_bomb/100lbs_aircraft_bomb.stl"), s=np.ones(3), A2B=tm.get_transform("target/100lbs", "world"))

fig.plot_transform(A2B=tm.get_transform("target/100lbs", "world"), s=0.2)

for index, row in df_ar3.iloc[::SCALING].iterrows():

    tm.add_transform("setup/ar3", "world", A2B=pytr.transform_from(R.from_quat(row[['rot.x','rot.y', 'rot.z', 'rot.w']]).as_matrix(), row[['pos.x','pos.y', 'pos.z']]))
    fig.plot_transform(A2B=tm.get_transform("setup/camera", "world"), s=0.2)

fig.show()

import cv2

ROOT_IMG = '/home/mbandefirvida/Documents/cleanseas/datasets/eggers_kampfmittelbergung-aris3000-black_basin/2023-09-20_171105/gopro/restored'
FRAME_ID = 1211
row = df_ar3[df_ar3.aris_frame_idx == FRAME_ID]
row

tm.add_transform("setup/ar3", "world", A2B=pytr.transform_from(R.from_quat(row[['rot.x','rot.y', 'rot.z', 'rot.w']]).as_matrix(), row[['pos.x','pos.y', 'pos.z']]))

ROOT_MESH = os.path.join('..', '..', '3d_models')
SCALING=20

fig = pv.figure()
fig.plot_mesh(filename=os.path.join(ROOT_MESH, "100lbs_aircraft_bomb/100lbs_aircraft_bomb.stl"), s=np.ones(3), A2B=tm.get_transform("target/100lbs", "world"))

fig.plot_transform(A2B=tm.get_transform("target/100lbs", "world"), s=0.2)
fig.plot_transform(A2B=tm.get_transform("setup/camera", "world"), s=0.2)

fig.show()

ROOT_IMG = '/home/mbandefirvida/Documents/cleanseas/datasets/eggers_kampfmittelbergung-aris3000-black_basin/2023-09-20_171105/gopro/restored'
image = cv2.imread(os.path.join(ROOT_IMG, str(FRAME_ID) + ".jpg"))
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# The following plots the waterfall-view in separate subplots
fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(gray)

import  apriltag

options = apriltag.DetectorOptions(families="tag36h11")
detector = apriltag.Detector(options)
results = detector.detect(gray)
print("[INFO] {} total AprilTags detected".format(len(results)))

for r in results:
  # extract the bounding box (x, y)-coordinates for the AprilTag
  # and convert each of the (x, y)-coordinate pairs to integers
  (ptA, ptB, ptC, ptD) = r.corners
  ptB = (int(ptB[0]), int(ptB[1]))
  ptC = (int(ptC[0]), int(ptC[1]))
  ptD = (int(ptD[0]), int(ptD[1]))
  ptA = (int(ptA[0]), int(ptA[1]))
  # draw the bounding box of the AprilTag detection
  cv2.line(image, ptA, ptB, (0, 255, 0), 2)
  cv2.line(image, ptB, ptC, (0, 255, 0), 2)
  cv2.line(image, ptC, ptD, (0, 255, 0), 2)
  cv2.line(image, ptD, ptA, (0, 255, 0), 2)
  # draw the center (x, y)-coordinates of the AprilTag
  (cX, cY) = (int(r.center[0]), int(r.center[1]))
  #cv2.circle(image, (cX, cY), 5, (0, 0, 255), -1)
  # draw the tag family on the image
  tagId = str(r.tag_id)
  tagFamily = r.tag_family.decode("utf-8")
  print(r.homography)
  cv2.putText(image, "Tag " + tagId, (cX, cY),
    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
  print("[INFO] tag family: {}".format(tagFamily))
# show the output image after AprilTag detection


fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image)

from mpl_toolkits.mplot3d.proj3d import proj_transform
from matplotlib.text import Annotation


class Annotation3D(Annotation):
    '''Annotate the point xyz with text s'''

    def __init__(self, s, xyz, *args, **kwargs):
        Annotation.__init__(self,s, xy=(0,0), *args, **kwargs)
        self._verts3d = xyz        

    def draw(self, renderer):
        xs, ys, zs = proj_transform(self._verts3d[0], self._verts3d[1], self._verts3d[2], renderer.M)
        self.xy=(xs,ys)
        Annotation.draw(self, renderer)
        
def annotate3D(ax, s, *args, **kwargs):
    '''add anotation text s to to Axes3d ax'''
    tag = Annotation3D(s, *args, **kwargs)
    ax.add_artist(tag)

# https://en.wikipedia.org/wiki/Camera_resectioning
K = np.array([[431.5790272011588, 0.0, 325.5650847006285],
              [0.0, 425.7563760783507, 160.3434930783429],
              [0.0, 0.0, 1.0]])

fx, fy = K[0,0], K[1,1]
cx, cy = K[2,0], K[2,1]


tfs = []
for result in results:
    pose = detector.detection_pose(result, [fx, fy, cx, cy],  tag_size=0.30)
    tf = pose[0]

    #NOTE: transform to camera frame
    tf[:3,3] = [-tf[1,3], tf[0,3], tf[2,3]]
    tfs.append(tf)

tfs = np.array(tfs)

np.array(tfs).round(4)

tf = tfs[0]
[tf[1,3], -tf[0,3], tf[2,3]]

for tf, result in zip(tfs,results):
    tf[:3,3] = [tf[3,1], -tf[3,0], tf[3,3]]
    print(tf)

from pytransform3d.plot_utils import make_3d_axis
import pytransform3d.transformations as pytr
from mpl_toolkits import mplot3d

figure = plt.figure(figsize=(10,10))
ax = mplot3d.Axes3D(figure)
ax = make_3d_axis(ax_s=10, unit="m", n_ticks=6)


for tf, result in zip(tfs,results):
    
    tm.add_transform("marker/" + str(result.tag_id), "setup/camera", A2B=tf)

    tf_from_world = tm.get_transform("marker/" + str(result.tag_id), "world")

    pytr.plot_transform(ax, A2B=tf_from_world, s=0.5)

    annotate3D(ax, s=str(result.tag_id), xyz=tf_from_world[:3,3], fontsize=10, xytext=(-3,3), textcoords='offset points', ha='right',va='bottom')
    break

pytr.plot_transform(ax, A2B=tm.get_transform("setup/camera", "world"), s=0.5)
pytr.plot_transform(ax, A2B=tm.get_transform("target/100lbs", "world"), s=0.5)
plt.show()

figure = plt.figure(figsize=(10,10))
ax = mplot3d.Axes3D(figure)
ax = make_3d_axis(ax_s=10, unit="m", n_ticks=6)

for i in range(1150,1228):
    row = df_ar3[df_ar3.aris_frame_idx == i]
    
    image = cv2.imread(os.path.join(ROOT_IMG, str(i) + ".jpg"))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    options = apriltag.DetectorOptions(families="tag36h11")
    detector = apriltag.Detector(options)
    results = detector.detect(gray)

    for result in results:
        if result.tag_id == 20:
            pose = detector.detection_pose(result, [fx, fy, cx, cy],  tag_size=0.247)
            
            tm.add_transform("setup/ar3", "world", A2B=pytr.transform_from(R.from_quat(row[['rot.x','rot.y', 'rot.z', 'rot.w']]).as_matrix(), row[['pos.x','pos.y', 'pos.z']]))

            tm.add_transform("marker/" + str(result.tag_id), "setup/camera", A2B=pose[0])

            tf_from_world = tm.get_transform("marker/" + str(result.tag_id), "world")

            pytr.plot_transform(ax, A2B=tf_from_world, s=0.25)
            pytr.plot_transform(ax, A2B=tm.get_transform("setup/camera", "world"), s=0.5)

    # annotate3D(ax, s=str(result.tag_id), xyz=tf_from_world[:3,3], fontsize=10, xytext=(-3,3), textcoords='offset points', ha='right',va='bottom')

pytr.plot_transform(ax, A2B=tm.get_transform("target/100lbs", "world"), s=0.5)
plt.show()



