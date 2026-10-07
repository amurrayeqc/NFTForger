import json
import tempfile
import unittest
from pathlib import Path
from nftforger import ForgeError, NFTForger

class TestNFTForger(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name); self.assets = self.root / "assets"; self.assets.mkdir()
        (self.assets / "one.png").write_bytes(b"fake-png-one"); (self.assets / "two.png").write_bytes(b"fake-png-two")
        self.config = self.root / "collection.json"; self.config.write_text(json.dumps({"collection": {"name": "Foundry", "description": "Forged items"}, "items": [{"token_id": 2, "name": "Two", "image": "two.png", "attributes": [{"trait_type": "Power", "value": 7}]}, {"token_id": 1, "name": "One", "image": "one.png"}]}))
        self.output = self.root / "build"; self.forger = NFTForger()
    def tearDown(self): self.temp.cleanup()

    def test_forges_sorted_metadata_assets_and_manifest(self):
        result = self.forger.forge(self.config, self.assets, self.output, "ipfs://CID/images")
        self.assertEqual(result["tokens"], 2); self.assertEqual(result["files"], 4)
        metadata = json.loads((self.output / "metadata/1.json").read_text()); self.assertEqual(metadata["image"], "ipfs://CID/images/one.png")
        manifest = json.loads((self.output / "manifest.json").read_text()); self.assertEqual([token["token_id"] for token in manifest["tokens"]], [1, 2])
        self.assertTrue(self.forger.verify(self.output)["valid"])

    def test_detects_asset_or_metadata_tampering(self):
        self.forger.forge(self.config, self.assets, self.output); (self.output / "metadata/1.json").write_text("tampered")
        result = self.forger.verify(self.output); self.assertFalse(result["valid"]); self.assertEqual(result["failures"][0]["error"], "hash mismatch")

    def test_rejects_duplicate_ids_unsafe_paths_and_missing_assets(self):
        data = json.loads(self.config.read_text()); data["items"][1]["token_id"] = 2; self.config.write_text(json.dumps(data))
        with self.assertRaisesRegex(ForgeError, "Duplicate"): self.forger.forge(self.config, self.assets, self.output)
        data["items"][1]["token_id"] = 1; data["items"][1]["image"] = "../secret.png"; self.config.write_text(json.dumps(data))
        with self.assertRaisesRegex(ForgeError, "unsafe"): self.forger.forge(self.config, self.assets, self.output)

    def test_refuses_overwrite_without_force(self):
        self.forger.forge(self.config, self.assets, self.output)
        with self.assertRaisesRegex(ForgeError, "already exists"): self.forger.forge(self.config, self.assets, self.output)
        result = self.forger.forge(self.config, self.assets, self.output, force=True); self.assertEqual(result["tokens"], 2)

if __name__ == "__main__": unittest.main()
