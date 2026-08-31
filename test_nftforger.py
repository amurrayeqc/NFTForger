# test_nftforger.py
"""
Tests for NFTForger module.
"""

import unittest
from nftforger import NFTForger

class TestNFTForger(unittest.TestCase):
    """Test cases for NFTForger class."""
    
    def test_initialization(self):
        """Test class initialization."""
        instance = NFTForger()
        self.assertIsInstance(instance, NFTForger)
        
    def test_run_method(self):
        """Test the run method."""
        instance = NFTForger()
        self.assertTrue(instance.run())

if __name__ == "__main__":
    unittest.main()
