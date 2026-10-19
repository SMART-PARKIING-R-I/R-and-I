import unittest
from unittest.mock import patch

import requests

from detector import SingleCameraWorker


class DetectorDispatchTests(unittest.TestCase):
    def test_retries_http_failure_after_cooldown(self):
        worker = SingleCameraWorker(
            {
                "camera_id": "CAM_BAC_MAIN",
                "lot_id": "BAC_PARKING",
                "source": 0,
                "spots_file": "configs/parking_spots.json",
            },
            shared_model=object(),
        )
        payload = {
            "camera_id": "CAM_BAC_MAIN",
            "lot_id": "BAC_PARKING",
            "spots": [{"spot_id": "A-001", "status": "occupied"}],
        }
        unavailable = requests.Response()
        unavailable.status_code = 503
        accepted = requests.Response()
        accepted.status_code = 200

        with (
            patch("detector.requests.post", side_effect=[unavailable, accepted]) as post,
            patch("detector.time.monotonic", side_effect=[10.0, 10.0, 10.5, 11.1]),
        ):
            worker.dispatch_payload(payload)
            worker.dispatch_payload(payload)
            self.assertIsNone(worker.last_sent_payload)
            worker.dispatch_payload(payload)

        self.assertEqual(post.call_count, 2)
        self.assertEqual(
            post.call_args.args[0],
            "http://127.0.0.1:5000/api/occupancy",
        )
        self.assertEqual(worker.last_sent_payload, payload)


if __name__ == "__main__":
    unittest.main()
