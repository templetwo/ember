"""Synthetic regressions for the no-name-gate, no-time-cut ruling."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from test_p0 import pair, splits, fixture_source_index, fixture_manifest
from ember import validation as v


class GroupSplitPolicyTests(unittest.TestCase):
    def test_sources_need_no_name_review_field(self):
        p=pair(1,'OPEN');index=fixture_source_index([p])
        for row in index['rows']:row.pop('name_screen',None)
        v.validate_source_index({'train':[p],'heldout':[]},index)

    def test_manifest_requires_group_policy_without_timestamp_cut(self):
        with tempfile.TemporaryDirectory() as folder:
            path,manifest=fixture_manifest(Path(folder))
            manifest.pop('freeze_at',None);manifest['split_strategy']='claim-groups'
            index=Path(folder)/manifest['source_index']['path']
            value=json.loads(index.read_text())
            for row in value['rows']:row.pop('name_screen',None)
            index.write_text(json.dumps(value));manifest['source_index']['sha256']=v.digest(index.read_bytes())
            receipt=Path(folder)/manifest['release_review']['receipt']['path']
            value=json.loads(receipt.read_text());value['source_index_sha256']=manifest['source_index']['sha256']
            receipt.write_text(json.dumps(value));manifest['release_review']['receipt']['sha256']=v.digest(receipt.read_bytes())
            path.write_text(json.dumps(manifest));v.load_manifest(path)
            manifest['freeze_at']='2026-10-01T00:00:00Z';path.write_text(json.dumps(manifest))
            with self.assertRaises(v.InvalidCorpus):v.load_manifest(path)

    def test_groups_can_be_assigned_regardless_of_calendar_order(self):
        train,held=splits()
        for p in train:
            p['recorded_at']='2026-10-15T13:00:00Z';p['evidence'][0]['recorded_at']=p['recorded_at']
        for p in held:
            p['recorded_at']='2026-08-01T13:00:00Z';p['evidence'][0]['recorded_at']=p['recorded_at']
        v.validate_split(train,held,4000)
        held[0]['review']['label_source_claim_id']=train[0]['review']['label_source_claim_id']
        with self.assertRaisesRegex(v.InvalidCorpus,'overlap'):v.validate_split(train,held,4000)

    def test_robot_reservation_still_cannot_enter_training(self):
        train,held=splits();reserved=[train[0]['review']['decision_claim_id']]
        with self.assertRaisesRegex(v.InvalidCorpus,'reserved robot'):
            v.validate_split(train,held,4000,reserved)

if __name__=='__main__':unittest.main()
