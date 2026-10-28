import hashlib
import json
import pathlib
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from run_continuous import archive_campaign, trim_archives


class ContinuousRetention(unittest.TestCase):
    def campaign(self, root):
        campaign = root/"campaigns"/"continuous-example"
        run = root/"runs"/"continuous-example-00-live"
        campaign.mkdir(parents=True)
        run.mkdir(parents=True)
        (run/"request.json").write_text('{"value": 17}\n')
        (campaign/"runs.json").write_text(json.dumps([str(run)]))
        (campaign/"outcome.json").write_text('{}')
        return campaign, run

    def test_archive_preserves_exact_bytes_and_unrelated_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            campaign, run = self.campaign(root)
            original = (run/"request.json").read_bytes()
            formal = root/"runs"/"validation-final"
            formal.mkdir()
            archive = archive_campaign(root, campaign)
            with tarfile.open(archive) as stream:
                self.assertEqual(stream.extractfile(
                    "runs/continuous-example-00-live/request.json").read(), original)
            self.assertFalse(run.exists())
            self.assertFalse(campaign.exists())
            self.assertTrue(formal.is_dir())
            expected = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(archive.with_suffix(archive.suffix+".sha256").read_text().split()[0], expected)

    def test_verification_failure_preserves_loose_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            campaign, run = self.campaign(root)
            with patch("run_continuous.verify_archive", side_effect=ValueError("corrupt archive")):
                with self.assertRaises(ValueError):
                    archive_campaign(root, campaign)
            self.assertTrue((run/"request.json").is_file())
            self.assertTrue((campaign/"outcome.json").is_file())

    def test_retention_removes_only_old_continuous_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            old = root/"continuous-old.tar.gz"
            old.write_bytes(b"old")
            old.with_suffix(".gz.sha256").write_text("hash")
            protected = root/"validation-final.tar.gz"
            protected.write_bytes(b"preserve")
            trim_archives(root, max_bytes=0)
            self.assertFalse(old.exists())
            self.assertFalse(old.with_suffix(".gz.sha256").exists())
            self.assertEqual(protected.read_bytes(), b"preserve")
