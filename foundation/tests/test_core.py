import unittest
from blackwolf.core import canonical_event, event_digest

class CoreTests(unittest.TestCase):
    def test_canonical_order(self):
        self.assertEqual(canonical_event({'b':2,'a':1}), canonical_event({'a':1,'b':2}))
    def test_stable_digest(self):
        self.assertEqual(event_digest({'a':1}), event_digest({'a':1}))
    def test_reject_non_finite(self):
        with self.assertRaises(ValueError):
            canonical_event({'bad': float('nan')})
    def test_reject_non_mapping(self):
        with self.assertRaises(TypeError):
            canonical_event([])

if __name__ == '__main__':
    unittest.main()
