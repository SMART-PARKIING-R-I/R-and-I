import unittest
from unittest.mock import patch

import numpy as np

import draw_spots


class DrawSpotsUndoTests(unittest.TestCase):
    def setUp(self):
        self.original_state = (
            draw_spots.current_polygon,
            draw_spots.all_spots,
            draw_spots.spot_counter,
            draw_spots.img,
            draw_spots.img_copy,
        )
        draw_spots.current_polygon = [[10, 20], [30, 40]]
        draw_spots.all_spots = []
        draw_spots.spot_counter = 1
        draw_spots.img = np.zeros((100, 100, 3), dtype=np.uint8)
        draw_spots.img_copy = None

    def tearDown(self):
        (
            draw_spots.current_polygon,
            draw_spots.all_spots,
            draw_spots.spot_counter,
            draw_spots.img,
            draw_spots.img_copy,
        ) = self.original_state

    def test_undo_last_corner_removes_only_current_polygon_point(self):
        with patch.object(draw_spots.cv2, "imshow"):
            undone = draw_spots.undo_last_corner()

        self.assertTrue(undone)
        self.assertEqual(draw_spots.current_polygon, [[10, 20]])

    def test_undo_last_completed_spot_reuses_next_available_id(self):
        draw_spots.all_spots = [
            {"spot_id": "A-001", "polygon": [[1, 1], [2, 1], [2, 2], [1, 2]]},
            {"spot_id": "A-004", "polygon": [[3, 3], [4, 3], [4, 4], [3, 4]]},
        ]
        draw_spots.spot_counter = 5

        with patch.object(draw_spots.cv2, "imshow"):
            undone = draw_spots.undo_last_spot()

        self.assertTrue(undone)
        self.assertEqual([spot["spot_id"] for spot in draw_spots.all_spots], ["A-001"])
        self.assertEqual(draw_spots.spot_counter, 2)
        draw_spots.current_polygon = []

        with (
            patch.object(draw_spots.cv2, "imshow"),
            patch.object(draw_spots.cv2, "polylines"),
            patch.object(draw_spots.cv2, "putText"),
            patch.object(draw_spots.cv2, "circle"),
            patch.object(draw_spots.cv2, "line"),
        ):
            draw_spots.click_event(draw_spots.cv2.EVENT_LBUTTONDOWN, 5, 5, 0, None)
            draw_spots.click_event(draw_spots.cv2.EVENT_LBUTTONDOWN, 15, 5, 0, None)
            draw_spots.click_event(draw_spots.cv2.EVENT_LBUTTONDOWN, 15, 15, 0, None)
            draw_spots.click_event(draw_spots.cv2.EVENT_LBUTTONDOWN, 5, 15, 0, None)

        self.assertEqual(draw_spots.all_spots[-1]["spot_id"], "A-002")


if __name__ == "__main__":
    unittest.main()
