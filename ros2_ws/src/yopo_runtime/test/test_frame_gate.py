import unittest
from yopo_runtime.frame_gate import FrameGate


class TimingTests(unittest.TestCase):
    def test_reordered_messages_pair_exactly_once(self):
        gate = FrameGate()
        gate.advance_clock(100)
        self.assertIsNone(gate.add("odometry", 100, "pose"))
        frame = gate.add("depth", 100, "image")
        self.assertEqual((frame.depth, frame.odometry, frame.observation_id), ("image", "pose", 1))
        self.assertIsNone(gate.add("depth", 100, "duplicate"))

    def test_mismatched_or_expired_or_future_frames_never_pair(self):
        gate = FrameGate(max_age_ns=5)
        gate.advance_clock(100)
        self.assertIsNone(gate.add("depth", 94, "stale"))
        self.assertIsNone(gate.add("depth", 101, "future"))
        gate.add("depth", 98, "image")
        self.assertIsNone(gate.add("odometry", 99, "other_pose"))
        gate.advance_clock(106)
        self.assertIsNone(gate.add("odometry", 98, "late_pose"))

    def test_clock_reversal_invalidates_buffer_and_old_plan(self):
        gate = FrameGate()
        gate.advance_clock(100)
        gate.add("depth", 100, "old")
        self.assertTrue(gate.trajectory_is_current(0, 90, 110))
        gate.advance_clock(0)
        self.assertEqual(gate.episode_id, 1)
        self.assertFalse(gate.trajectory_is_current(0, 0, 1000))
        self.assertIsNone(gate.add("odometry", 0, "new_pose"))
        frame = gate.add("depth", 0, "new_depth")
        self.assertEqual(frame.episode_id, 1)
        self.assertEqual(frame.depth, "new_depth")

    def test_validity_end_is_exclusive_and_queue_is_bounded(self):
        gate = FrameGate(capacity=2)
        gate.advance_clock(100)
        for t in (97, 98, 99):
            gate.add("depth", t, t)
        self.assertIsNone(gate.add("odometry", 97, "evicted"))
        self.assertFalse(gate.trajectory_is_current(0, 80, 100))


if __name__ == "__main__":
    unittest.main()
