from __future__ import absolute_import, division, print_function, unicode_literals

import unittest

import numpy as np
import torch
from tests.utils import jitVsGlow


def generate_rois(roi_counts, im_dims):
    assert len(roi_counts) == len(im_dims)
    all_rois = []
    for i, num_rois in enumerate(roi_counts):
        if num_rois == 0:
            continue
        # [batch_idx, x1, y1, x2, y2]
        rois = np.random.uniform(0, im_dims[i], size=(roi_counts[i], 5)).astype(
            np.float32
        )
        rois[:, 0] = i  # batch_idx
        # Swap (x1, x2) if x1 > x2
        rois[:, 1], rois[:, 3] = (
            np.minimum(rois[:, 1], rois[:, 3]),
            np.maximum(rois[:, 1], rois[:, 3]),
        )
        # Swap (y1, y2) if y1 > y2
        rois[:, 2], rois[:, 4] = (
            np.minimum(rois[:, 2], rois[:, 4]),
            np.maximum(rois[:, 2], rois[:, 4]),
        )
        all_rois.append(rois)
    if len(all_rois) > 0:
        return np.vstack(all_rois)
    return np.empty((0, 5)).astype(np.float32)


def generate_rois_rotated(roi_counts, im_dims):
    rois = generate_rois(roi_counts, im_dims)
    # [batch_id, ctr_x, ctr_y, w, h, angle]
    rotated_rois = np.empty((rois.shape[0], 6)).astype(np.float32)
    rotated_rois[:, 0] = rois[:, 0]  # batch_id
    rotated_rois[:, 1] = (rois[:, 1] + rois[:, 3]) / 2.0  # ctr_x = (x1 + x2) / 2
    rotated_rois[:, 2] = (rois[:, 2] + rois[:, 4]) / 2.0  # ctr_y = (y1 + y2) / 2
    rotated_rois[:, 3] = rois[:, 3] - rois[:, 1] + 1.0  # w = x2 - x1 + 1
    rotated_rois[:, 4] = rois[:, 4] - rois[:, 2] + 1.0  # h = y2 - y1 + 1
    rotated_rois[:, 5] = np.random.uniform(-90.0, 90.0)  # angle in degrees
    return rotated_rois


def create_bbox_transform_inputs(roi_counts, num_classes, rotated):
    batch_size = len(roi_counts)
    total_rois = sum(roi_counts)
    im_dims = np.random.randint(100, 600, batch_size)
    rois = (
        generate_rois_rotated(roi_counts, im_dims)
        if rotated
        else generate_rois(roi_counts, im_dims)
    )
    box_dim = 5 if rotated else 4
    deltas = np.random.randn(total_rois, box_dim * num_classes).astype(np.float32)
    im_info = np.zeros((batch_size, 3)).astype(np.float32)
    im_info[:, 0] = im_dims
    im_info[:, 1] = im_dims
    im_info[:, 2] = np.random.random()
    return rois, deltas, im_info


class TestBBoxTransform(unittest.TestCase):
    def test_bbox_transform_basic(self):
        """Test of the _caffe2::BBoxTransform Node on Glow."""

        def test_f(rois, deltas, im_info):
            return torch.ops._caffe2.BBoxTransform(
                rois,
                deltas,
                im_info,
                weights=[1.0, 1.0, 1.0, 1.0],
                apply_scale=False,
                rotated=False,
                angle_bound_on=False,
                angle_bound_lo=-90,
                angle_bound_hi=90,
                clip_angle_thresh=1.0,
                legacy_plus_one=False,
            )

        roi_counts, num_classes = ([5, 4, 3, 2, 1], 3)
        rois, deltas, im_info = create_bbox_transform_inputs(
            roi_counts, num_classes, False
        )
        jitVsGlow(
            test_f,
            torch.tensor(rois),
            torch.tensor(deltas),
            torch.tensor(im_info),
            expected_fused_ops={"_caffe2::BBoxTransform"},
        )

    def test_bbox_transform_basic_legacy_plus_one(self):
        """Test of the _caffe2::BBoxTransform Node on Glow."""

        def test_f(rois, deltas, im_info):
            return torch.ops._caffe2.BBoxTransform(
                rois,
                deltas,
                im_info,
                weights=[1.0, 1.0, 1.0, 1.0],
                apply_scale=False,
                rotated=False,
                angle_bound_on=False,
                angle_bound_lo=-90,
                angle_bound_hi=90,
                clip_angle_thresh=1.0,
                legacy_plus_one=True,
            )

        roi_counts, num_classes = ([5, 4, 3, 2, 1], 3)
        rois, deltas, im_info = create_bbox_transform_inputs(
            roi_counts, num_classes, False
        )
        jitVsGlow(
            test_f,
            torch.tensor(rois),
            torch.tensor(deltas),
            torch.tensor(im_info),
            expected_fused_ops={"_caffe2::BBoxTransform"},
        )

    def test_bbox_transform_apply_scale(self):
        """Test of the _caffe2::BBoxTransform Node on Glow."""

        def test_f(rois, deltas, im_info):
            return torch.ops._caffe2.BBoxTransform(
                rois,
                deltas,
                im_info,
                weights=[1.0, 1.0, 1.0, 1.0],
                apply_scale=True,
                rotated=False,
                angle_bound_on=False,
                angle_bound_lo=-90,
                angle_bound_hi=90,
                clip_angle_thresh=1.0,
                legacy_plus_one=False,
            )

        roi_counts, num_classes = ([5, 4, 3, 2, 1], 3)
        rois, deltas, im_info = create_bbox_transform_inputs(
            roi_counts, num_classes, False
        )
        jitVsGlow(
            test_f,
            torch.tensor(rois),
            torch.tensor(deltas),
            torch.tensor(im_info),
            expected_fused_ops={"_caffe2::BBoxTransform"},
        )

    def test_bbox_transform_weights(self):
        """Test of the _caffe2::BBoxTransform Node on Glow."""

        def test_f(rois, deltas, im_info):
            return torch.ops._caffe2.BBoxTransform(
                rois,
                deltas,
                im_info,
                weights=[10.0, 10.0, 5.0, 5.0],
                apply_scale=False,
                rotated=False,
                angle_bound_on=False,
                angle_bound_lo=-90,
                angle_bound_hi=90,
                clip_angle_thresh=1.0,
                legacy_plus_one=False,
            )

        roi_counts, num_classes = ([5, 4, 3, 2, 1], 3)
        rois, deltas, im_info = create_bbox_transform_inputs(
            roi_counts, num_classes, False
        )
        jitVsGlow(
            test_f,
            torch.tensor(rois),
            torch.tensor(deltas),
            torch.tensor(im_info),
            expected_fused_ops={"_caffe2::BBoxTransform"},
        )

    def test_bbox_transform_fp16(self):
        """Test of the _caffe2::BBoxTransform Node on Glow."""

        def test_f(rois, deltas, im_info):
            return torch.ops._caffe2.BBoxTransform(
                rois,
                deltas,
                im_info,
                weights=[1.0, 1.0, 1.0, 1.0],
                apply_scale=False,
                rotated=False,
                angle_bound_on=False,
                angle_bound_lo=-90,
                angle_bound_hi=90,
                clip_angle_thresh=1.0,
                legacy_plus_one=False,
            )

        roi_counts, num_classes = ([5, 4, 3, 2, 1], 3)
        rois, deltas, im_info = create_bbox_transform_inputs(
            roi_counts, num_classes, False
        )
        jitVsGlow(
            test_f,
            torch.tensor(rois),
            torch.tensor(deltas),
            torch.tensor(im_info),
            expected_fused_ops={"_caffe2::BBoxTransform"},
            use_fp16=True,
            atol=1,
            rtol=1e-02,
        )
