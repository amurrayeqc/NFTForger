# NFTForger

[![CI](https://github.com/centxyz/NFTForger/actions/workflows/ci.yml/badge.svg)](https://github.com/centxyz/NFTForger/actions/workflows/ci.yml)

NFTForger validates and packages NFT collections into deterministic ERC-721 metadata builds. It copies verified local media, emits one metadata document per token, creates a SHA-256 integrity manifest, and can later detect missing or modified files.

It does not upload content, mint tokens, hold keys, or imply that generated metadata has market value.

## Collection config

```json
{
  "collection": {
    "name": "Foundry Collection",
    "description": "Artifacts from the foundry"
  },
  "items": [
    {
      "token_id": 1,
      "name": "Artifact #1",
      "image": "artifact-1.png",
      "attributes": [
        { "trait_type": "Material", "value": "Obsidian" },
        { "trait_type": "Power", "value": 9 }
      ]
    }
  ]
}
```

Image paths must stay inside the supplied assets directory. Token IDs must be unique non-negative integers, and every attribute requires `trait_type` and `value`.

## Forge and verify

```bash
python nftforger.py forge \
  --config collection.json \
  --assets ./assets \
  --output ./build \
  --image-base-uri ipfs://YOUR_DIRECTORY_CID/images

python nftforger.py verify --output ./build
```

The output contains `images/`, `metadata/<token_id>.json`, and `manifest.json`. Existing output is protected unless `--force` is explicit. Builds are assembled in a staging directory and moved into place only after every item succeeds.

When using IPFS, the final directory CID is not known until upload. You can first forge with the default relative image paths, upload assets, then forge again with the final base URI before uploading the complete build.

## Test

```bash
python -m unittest discover -v
```

## License

MIT © cent

## Current limitations

- It packages and verifies local files but does not upload content, pin IPFS data, mint tokens, or manage keys.
- A valid local manifest does not guarantee long-term media availability after deployment.
- Users must review metadata, licensing, storage, and contract behavior independently.
