#!/usr/bin/env python3
"""Estimate robot pose in an AprilTag-defined area with perspective correction.

Setup expected by user:
- Robot tag: ID 0
- Area corner tags: IDs 1,2,3,4
- Dictionary: APRILTAG_36h11
- Area size: A2 (594x420 mm or 420x594 mm auto-selected by geometry)

Features
- Optional camera distortion correction from OpenCV calibration npz/yaml.
- Perspective warp (bird's-eye) from area outer corners.
- Robot (x,y,theta) in area coordinates.
- Output images:
  - debug image (original + selected corners)
  - warped area image with robot pose overlay

Usage example:
  python scripts/apriltag_area_pose.py \
    --cam-index 0 \
    --out-debug apriltag_debug.png \
    --out-warp apriltag_warp.png
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def load_calib(path: Optional[Path]):
    if path is None or not path.exists():
        return None, None
    if path.suffix.lower() == ".npz":
        d = np.load(str(path))
        k = d.get("camera_matrix")
        dist = d.get("dist_coeffs")
        return k, dist
    fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        return None, None
    k = fs.getNode("camera_matrix").mat()
    dist = fs.getNode("dist_coeffs").mat()
    fs.release()
    return k, dist


def order_corners(pts: np.ndarray) -> np.ndarray:
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]  # TL
    ordered[2] = pts[np.argmax(s)]  # BR
    ordered[1] = pts[np.argmin(d)]  # TR
    ordered[3] = pts[np.argmax(d)]  # BL
    return ordered


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cam-index", type=int, default=0)
    p.add_argument("--dict", default="DICT_APRILTAG_36h11")
    p.add_argument("--robot-id", type=int, default=0)
    p.add_argument("--area-ids", default="1,2,3,4")
    p.add_argument("--a2-width-mm", type=float, default=594.0)
    p.add_argument("--a2-height-mm", type=float, default=420.0)
    p.add_argument("--scale", type=float, default=2.0, help="warp pixels per mm")
    p.add_argument("--calib", type=Path, default=None, help="optional camera calib npz/yaml")
    p.add_argument("--out-debug", type=Path, default=Path("apriltag_area_debug.png"))
    p.add_argument("--out-warp", type=Path, default=Path("apriltag_area_warp.png"))
    args = p.parse_args(argv)

    area_ids = [int(x.strip()) for x in str(args.area_ids).split(",") if x.strip()]
    if len(area_ids) != 4:
        raise SystemExit("area-ids must contain exactly 4 ids")

    cap = cv2.VideoCapture(int(args.cam_index))
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise SystemExit("camera capture failed")

    k, dist = load_calib(args.calib)
    img = frame
    if k is not None and dist is not None:
        img = cv2.undistort(frame, k, dist)

    aruco = cv2.aruco
    if not hasattr(aruco, args.dict):
        raise SystemExit(f"unknown dict: {args.dict}")
    dict_id = getattr(aruco, args.dict)
    dic = aruco.getPredefinedDictionary(dict_id)
    params = aruco.DetectorParameters()
    params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
    det = aruco.ArucoDetector(dic, params)

    corners, ids, _ = det.detectMarkers(img)
    debug = img.copy()

    if ids is None or len(ids) == 0:
        cv2.putText(debug, "NO_TAGS", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imwrite(str(args.out_debug), debug)
        return 0

    id_list = [int(x[0]) for x in ids]
    marker = {}
    centers = {}
    for c, tid in zip(corners, id_list):
        p4 = c.reshape(4, 2).astype(np.float32)
        marker[tid] = p4
        centers[tid] = p4.mean(axis=0)
        cv2.polylines(debug, [p4.astype(int)], True, (0, 255, 0), 2)
        cv2.putText(debug, f"ID{tid}", tuple(centers[tid].astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    required = set(area_ids + [int(args.robot_id)])
    missing = sorted(list(required - set(id_list)))
    if missing:
        cv2.putText(debug, f"MISSING {missing}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imwrite(str(args.out_debug), debug)
        return 0

    # Area polygon from OUTER corners (farthest from area-center), as requested
    area_centers = np.array([centers[i] for i in area_ids], dtype=np.float32)
    C = area_centers.mean(axis=0)
    outer = []
    for tid in area_ids:
        p = marker[tid]
        d2 = ((p - C) ** 2).sum(axis=1)
        outer.append(p[np.argmax(d2)])
    outer = np.array(outer, dtype=np.float32)
    area_ord = order_corners(outer)

    for i, pxy in enumerate(area_ord.astype(int)):
        cv2.circle(debug, tuple(pxy), 7, (255, 0, 255), -1)
        cv2.putText(debug, ["TL", "TR", "BR", "BL"][i], tuple(pxy + np.array([8, -8])), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
    cv2.polylines(debug, [area_ord.astype(int)], True, (255, 0, 0), 2)

    # A2 orientation auto by side lengths
    w_px = float(np.linalg.norm(area_ord[1] - area_ord[0]))
    h_px = float(np.linalg.norm(area_ord[3] - area_ord[0]))
    if w_px >= h_px:
        W_mm, H_mm = float(args.a2_width_mm), float(args.a2_height_mm)
    else:
        W_mm, H_mm = float(args.a2_height_mm), float(args.a2_width_mm)

    scale = float(args.scale)
    W = int(W_mm * scale)
    H = int(H_mm * scale)
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(area_ord, dst)
    warp = cv2.warpPerspective(img, M, (W, H))

    # Robot pose from ID0 marker
    p0 = marker[int(args.robot_id)]
    ctr = p0.mean(axis=0)
    front = (p0[0] + p0[1]) * 0.5  # top edge midpoint as heading direction

    ctr_h = np.array([ctr[0], ctr[1], 1.0], dtype=np.float32)
    fr_h = np.array([front[0], front[1], 1.0], dtype=np.float32)
    rb = M @ ctr_h
    rf = M @ fr_h
    rb = rb[:2] / rb[2]
    rf = rf[:2] / rf[2]

    # convert to mm coordinates
    rb_mm = rb / scale
    rf_mm = rf / scale
    v = rf_mm - rb_mm
    theta = math.degrees(math.atan2(v[1], v[0]))

    # Draw robot on debug
    cv2.circle(debug, tuple(ctr.astype(int)), 6, (0, 0, 255), -1)
    cv2.arrowedLine(debug, tuple(ctr.astype(int)), tuple(front.astype(int)), (0, 0, 255), 2, tipLength=0.3)

    txt = f"Robot x={rb_mm[0]:.1f}mm y={rb_mm[1]:.1f}mm th={theta:.1f}deg"
    cv2.putText(debug, txt, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
    cv2.putText(debug, f"A2 {int(W_mm)}x{int(H_mm)}mm (outer corners)", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)

    # Draw robot on warp
    rbi = tuple((rb).astype(int))
    rfi = tuple((rf).astype(int))
    cv2.circle(warp, rbi, 8, (0, 0, 255), -1)
    cv2.arrowedLine(warp, rbi, rfi, (0, 0, 255), 2, tipLength=0.3)
    cv2.putText(warp, txt, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    args.out_debug.parent.mkdir(parents=True, exist_ok=True)
    args.out_warp.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.out_debug), debug)
    cv2.imwrite(str(args.out_warp), warp)

    print(txt)
    print(f"wrote {args.out_debug}")
    print(f"wrote {args.out_warp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
