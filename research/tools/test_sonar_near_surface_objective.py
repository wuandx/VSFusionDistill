"""Small synthetic controls for the new front-surface objective semantics."""
import sys
import unittest
sys.dont_write_bytecode=True
import numpy as np
from fit_sonar_fixed_registration_refinement import FrontFrame,adapt_observations


class NearSurfaceTests(unittest.TestCase):
    def frame(self,interval=(100.,100.),edges=None):
        f=FrontFrame.__new__(FrontFrame)
        f.observation=dict(points=[dict(beam_window=[48.5,51.5],range_interval=list(interval),witness_raw_uv_edge=[50.,100.])],
                           weak_echo_edges=edges or dict(left=None,right=None))
        return f

    def projected(self,uv):
        return dict(uv=np.asarray(uv,dtype=float).reshape(-1,2),visible=np.ones(len(uv),dtype=bool))

    def test_front_cannot_be_replaced_by_any_included_surface_point(self):
        f=self.frame()
        self.assertEqual(f.loss(self.projected([[50,100]])),0)
        self.assertGreater(f.loss(self.projected([[50,80],[50,100],[50,140]])),4)

    def test_frozen_interval_and_missing_beam(self):
        f=self.frame((96.,104.))
        self.assertEqual(f.loss(self.projected([[50,101]])),0)
        self.assertGreater(f.loss(self.projected([[50,110]])),0)
        self.assertGreater(f.loss(self.projected([[60,101]])),0)
        self.assertGreater(f.loss(self.projected([])),100)

    def test_weak_edges_are_separate_low_weight_terms(self):
        f=self.frame(edges=dict(left=[40,45],right=[55,60]))
        result=f.loss(self.projected([[50,100]]),details=True)
        self.assertEqual(result['near_surface_objective'],0)
        self.assertGreater(result['weak_edge_objective'],0)
        self.assertAlmostEqual(result['objective'],.1*result['weak_edge_objective'])

    def test_mortar_eligibility_interval_and_censoring(self):
        point=dict(raw_uv_edge=[49.5,162.5],observation_box_raw_edges=[48,160,51,176],eligible_for_main_curve=True)
        excluded=dict(point,eligible_for_main_curve=False)
        observations=dict(frames=[dict(sample='synthetic',points=[point,excluded])])
        companion=dict(frames=[dict(sample='synthetic',possible_horizontal_fov_censoring=True,
                                   echo_left_disappearance_beam_interval=[0,18],echo_right_disappearance_beam_interval=[114,128])])
        adapted=adapt_observations('mortar_shell',observations,companion)
        self.assertEqual(adapted['point_count'],1);self.assertEqual(adapted['excluded_point_count'],1)
        f=adapted['frames'][0]
        self.assertEqual(f['points'][0]['range_interval'],[160.,176.])
        self.assertEqual(f['weak_echo_edges'],dict(left=None,right=None))

    def test_bomb_interval_uses_frozen_range_and_censored_edges(self):
        point=dict(raw_uv_edge=[12.5,190.5],near_range_bin_interval=[187,194])
        observations=dict(frames=[dict(sample='center',points=[point],possible_fov_truncation=['right_observed'],
                                      lateral_visible_echo_edge_intervals_raw_u=dict(left=None,right=None)),
                                  dict(sample='neighbor',points=[])])
        adapted=adapt_observations('100lbs',observations,None)
        self.assertEqual(len(adapted['frames']),1)
        row=adapted['frames'][0]
        self.assertEqual(row['points'][0]['range_interval'],[187.,194.])
        self.assertEqual(row['points'][0]['beam_window'],[11.,14.])
        self.assertTrue(row['fov_censored'])
        self.assertEqual(row['weak_echo_edges'],dict(left=None,right=None))


if __name__=='__main__':unittest.main(verbosity=2)
