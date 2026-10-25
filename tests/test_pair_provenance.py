"""Synthetic review regressions; never source records or training examples."""
import copy
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ember import validation
from ember.baselines import run_baselines
from ember.validation import InvalidCorpus, validate_pair, validate_split
from test_p0 import pair, splits, CUT, fixture_manifest
import tempfile

LABEL = 'abcdef0123456789' * 4


def set_text(p, field, value):
    if field == 'situation': p['situation'] = value
    elif field == 'evidence': p['evidence'][0]['text'] = value
    else: p['target']['rationale'] = value


class LabelLeakTests(unittest.TestCase):
    def test_full_and_every_hex_prefix_at_least_twelve_refused_in_all_text(self):
        for field in ('situation', 'evidence', 'rationale'):
            for size in range(12,65):
                p = pair(1,'PAUSE');p['review']['label_source_claim_id'] = LABEL
                set_text(p,field,'Source reference: '+LABEL[:size])
                with self.subTest(field=field,size=size), self.assertRaisesRegex(InvalidCorpus,'label source'):
                    validate_pair(p,4000)

    def test_case_and_whitespace_variants_are_refused(self):
        for field in ('situation','evidence','rationale'):
            for fragment in (LABEL, LABEL[:12]):
                p=pair(1,'PAUSE');p['review']['label_source_claim_id']=' \t'+LABEL.upper()+'\n'
                set_text(p,field,'Source: '+' \n'.join(fragment.upper()))
                with self.subTest(field=field,size=len(fragment)),self.assertRaisesRegex(InvalidCorpus,'label source'):
                    validate_pair(p,4000)

    def test_short_or_different_hex_prefix_does_not_match(self):
        for fragment in (LABEL[:11], '0'+LABEL[1:12]):
            p=pair(1,'PAUSE');p['review']['label_source_claim_id']=LABEL
            p['situation']='Synthetic fixture '+fragment
            validate_pair(p,4000)

    def test_nonhex_full_label_id_is_still_refused(self):
        p=pair(1,'PAUSE');p['situation']=p['review']['label_source_claim_id'].upper()
        with self.assertRaisesRegex(InvalidCorpus,'label source'):validate_pair(p,4000)

    def test_structured_label_alias_and_prefix_are_refused(self):
        for value in (' \n'+LABEL.upper()+'\t', LABEL[:12]):
            p=pair(1,'PAUSE');p['review']['label_source_claim_id']=LABEL
            p['evidence'][0]['claim_id']=value
            p['source_claim_ids']=[value];p['target']['cited_claim_ids']=[value]
            with self.assertRaisesRegex(InvalidCorpus,'label source'):validate_pair(p,4000)

    def test_normalized_duplicate_evidence_is_refused(self):
        p=pair(1,'PAUSE');extra=copy.deepcopy(p['evidence'][0]);extra['claim_id']=' '+extra['claim_id'].upper()+' '
        p['evidence'].append(extra)
        with self.assertRaisesRegex(InvalidCorpus,'duplicate evidence'):validate_pair(p,4000)

    def test_normalized_label_overlap_is_refused_across_splits(self):
        train,held=splits();held[0]['review']['label_source_claim_id']=' '+train[0]['review']['label_source_claim_id'].upper()+' '
        with self.assertRaisesRegex(InvalidCorpus,'overlap'):validate_split(train,held,4000)


class ObservedDecisionTests(unittest.TestCase):
    def test_observed_act_is_required_without_guessing(self):
        p=pair(1,'OPEN');p['review'].pop('observed_act',None)
        with self.assertRaises(InvalidCorpus):validate_pair(p,4000)

    def test_three_agreeing_decisions_are_admitted(self):
        train,held=splits()
        for p in train+held:
            p['pair_class']='observed-decision'
            p['review']['observed_act']='proceed' if p['target']['decision']=='OPEN' else 'stop'
        validate_split(train,held,4000,pair_classes=['observed-decision'])

    def test_disagreement_flags_are_derived_and_refused_in_either_split(self):
        for label,act,flag in (('OPEN','stop','over-stop'),('PAUSE','proceed','hindsight-stop'),('WITNESS','proceed','hindsight-stop')):
            p=pair(99,label);p['review']['observed_act']=act
            self.assertEqual(validation.decision_flags(p),[flag])
            with self.assertRaisesRegex(InvalidCorpus,'observed act'):validate_pair(p,4000)
            for index in (0,1):
                train,held=splits();(train,held)[index][0]['target']['decision']=label
                (train,held)[index][0]['review']['observed_act']=act
                with self.subTest(label=label,index=index),self.assertRaisesRegex(InvalidCorpus,'observed act'):
                    validate_split(train,held,4000)

    def test_manifest_passes_its_class_constraint_to_split_validator(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,manifest=fixture_manifest(Path(temporary))
            with patch('ember.validation.validate_split') as split:
                validation.load_manifest(path)
            self.assertEqual(split.call_args.kwargs['pair_classes'],manifest['constraints']['pair_classes'])

    def test_empty_or_ineligible_admission_constraint_is_refused(self):
        for classes in ([],['retrospective-rule']):
            train,held=splits()
            with self.assertRaises(InvalidCorpus):validate_split(train,held,4000,pair_classes=classes)

    def test_baseline_counts_bind_label_shape_and_class_without_text(self):
        train,held=splits();train[0]['shape']='judged_gate';held[0]['shape']='ruling'
        result=run_baselines(train,held)
        table=result['label_shape_class_counts']
        for name,rows in (('train',train),('heldout',held)):
            self.assertEqual(sum(r['count'] for r in table[name]),len(rows))
            expected=sorted((p['target']['decision'],p['shape'],p['pair_class']) for p in rows)
            actual=sorted((r['label'],r['shape'],r['pair_class']) for r in table[name] for _ in range(r['count']))
            self.assertEqual(actual,expected)
        self.assertNotIn('situation',str(table))

if __name__=='__main__':unittest.main()
