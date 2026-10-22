import unittest
from unittest.mock import Mock, patch

import detector
import numpy as np
from detector import SingleCameraWorker


class DetectorSourceTests(unittest.TestCase):
    def setUp(self):
        self.camera_config = {
            "camera_id": "CAM_NEW_LOT_1",
            "lot_id": "SECONDARY_LOT",
            "source": "Lot_2_empty.png",
            "spots_file": "configs/lot_B.json",
        }
        self.worker = SingleCameraWorker(self.camera_config, shared_model=object())
        self.frame = object()
        self.payload = {
            "camera_id": "CAM_NEW_LOT_1",
            "lot_id": "SECONDARY_LOT",
            "spots": [{"spot_id": "A-001", "status": "vacant"}],
        }

    def test_image_source_is_processed_once_without_video_capture(self):
        with (
            patch.object(detector.cv2, "imread", return_value=self.frame) as imread,
            patch.object(detector.cv2, "VideoCapture") as video_capture,
            patch.object(
                self.worker,
                "process_frame",
                return_value=(self.frame, self.payload),
            ) as process_frame,
            patch.object(self.worker, "dispatch_payload") as dispatch,
            patch.object(detector.cv2, "namedWindow") as named_window,
            patch.object(detector.cv2, "resizeWindow") as resize_window,
            patch.object(detector.cv2, "imshow") as imshow,
            patch.object(detector.cv2, "waitKey", return_value=ord("q")),
            patch.object(detector.cv2, "destroyWindow") as destroy_window,
        ):
            self.worker.run()

        imread.assert_called_once_with(
            detector.os.path.join(detector.BASE_DIR, "Lot_2_empty.png")
        )
        video_capture.assert_not_called()
        process_frame.assert_called_once_with(self.frame, smooth=False)
        dispatch.assert_called_once_with(self.payload)
        named_window.assert_called_once_with(
            "Feed: CAM_NEW_LOT_1 (SECONDARY_LOT)",
            detector.cv2.WINDOW_NORMAL,
        )
        resize_window.assert_called_once_with(
            "Feed: CAM_NEW_LOT_1 (SECONDARY_LOT)",
            1920,
            1080,
        )
        imshow.assert_called_once()
        destroy_window.assert_called_once()

    def test_live_camera_preview_requests_1920_by_1080(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.side_effect = [(True, self.frame), (False, None)]
        self.worker.source = 0

        with (
            patch.object(detector.cv2, "VideoCapture", return_value=capture),
            patch.object(
                self.worker,
                "process_frame",
                return_value=(self.frame, self.payload),
            ),
            patch.object(self.worker, "dispatch_payload"),
            patch.object(detector.cv2, "namedWindow") as named_window,
            patch.object(detector.cv2, "resizeWindow") as resize_window,
            patch.object(detector.cv2, "imshow"),
            patch.object(detector.cv2, "waitKey", return_value=0),
            patch.object(detector.cv2, "destroyWindow"),
        ):
            self.worker.run()

        named_window.assert_called_once_with(
            "Feed: CAM_NEW_LOT_1 (SECONDARY_LOT)",
            detector.cv2.WINDOW_NORMAL,
        )
        resize_window.assert_called_once_with(
            "Feed: CAM_NEW_LOT_1 (SECONDARY_LOT)",
            1920,
            1080,
        )

    def test_unreadable_camera_frame_does_not_destroy_uncreated_window(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (False, None)

        with (
            patch.object(detector.cv2, "VideoCapture", return_value=capture),
            patch.object(detector.cv2, "imshow") as imshow,
            patch.object(detector.cv2, "destroyWindow") as destroy_window,
        ):
            self.worker.source = 0
            self.worker.run()

        capture.release.assert_called_once()
        imshow.assert_not_called()
        destroy_window.assert_not_called()

    def test_process_frame_scales_spots_to_camera_resolution(self):
        self.worker.coordinate_reference_size = (1278, 749)
        self.worker.model = Mock(return_value=[Mock(boxes=[])])
        frame = np.zeros((480, 640, 3), dtype="uint8")
        first_spot = self.worker.spots[0]

        with patch.object(detector.cv2, "polylines") as draw_polygon:
            self.worker.process_frame(frame)

        drawn_points = draw_polygon.call_args.args[1][0].reshape((-1, 2))
        expected = [
            [round(x * 640 / 1278), round(y * 480 / 749)]
            for x, y in first_spot["raw_coords"]
        ]
        self.assertEqual(drawn_points.tolist(), expected)
        self.assertLessEqual(drawn_points[:, 0].max(), 639)
        self.assertLessEqual(drawn_points[:, 1].max(), 479)


if __name__ == "__main__":
    unittest.main()
