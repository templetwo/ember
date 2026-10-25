"""Synthetic precision-source regressions for the L1b independent review."""
import copy
import unittest
from test_p0 import pair, splits, CUT, fixture_source_index
from test_temporal_sources import index_for
from ember import validation as v


def clock_pair():
    p=pair(1,'PAUSE','2026-09-10T13:00:00Z')
    return p


def day_case():
    p=clock_pair();p['review'].pop('decision_claim_id')
    p['recorded_at_precision']='day';p['recorded_at']='2026-09-10T04:00:00Z'
    p['evidence'][0]['recorded_at']='2026-09-09T13:00:00Z'
    p['review'].update(event_date='2026-09-10',event_date_claim_ids=[p['evidence'][0]['claim_id']])
    index=index_for(p)
    index['rows'][1]['decision_day_review']={'event_date':'2026-09-10',
        'claim_ids':p['review']['event_date_claim_ids'],'reader':'fixture','receipt':'fixture-only'}
    return p,index


class ClockProvenanceTests(unittest.TestCase):
    def test_clock_without_decision_source_is_refused(self):
        p=clock_pair();p['review'].pop('decision_claim_id')
        with self.assertRaises(v.InvalidCorpus):v.validate_pair(p,4000)

    def test_midnight_cannot_masquerade_as_clock(self):
        for stamp in ('2026-09-10T00:00:00Z','2026-09-10T04:00:00Z',
                      '2026-02-10T05:00:00Z','2026-09-10T20:00:00-04:00'):
            p=clock_pair();p['recorded_at']=stamp;p['evidence'][0]['recorded_at']='2026-01-01T13:00:00Z'
            with self.subTest(stamp=stamp),self.assertRaisesRegex(v.InvalidCorpus,'midnight'):
                v.validate_pair(p,4000)

    def test_clock_source_instant_and_all_eligibility_gates(self):
        p=clock_pair();index=index_for(p);rows={'train':[p],'heldout':[]}
        v.validate_pair(p,4000);v.validate_source_index(rows,index)
        for key,value in (('source_utc','2026-09-10T12:00:00Z'),('seed_backfill',True),
                          ('review_holds',['held']),('source_utc',None)):
            changed=copy.deepcopy(index);changed['rows'][0][key]=value
            with self.subTest(key=key),self.assertRaises(v.InvalidCorpus):v.validate_source_index(rows,changed)
        changed=copy.deepcopy(index);changed['rows'][0]['name_screen']['status']='pending'
        with self.assertRaises(v.InvalidCorpus):v.validate_source_index(rows,changed)
        p['review']['decision_claim_id']='absent'
        with self.assertRaisesRegex(v.InvalidCorpus,'decision.*absent'):v.validate_source_index(rows,index)

    def test_clock_source_can_be_metadata_only_but_must_be_unique(self):
        p=clock_pair();index=index_for(p)
        proof=copy.deepcopy(index['rows'][0]);proof.update(source_row_id='clock-proof-row',claim_id='clock-proof')
        index['rows'].append(proof);p['review']['decision_claim_id']='clock-proof'
        rows={'train':[p],'heldout':[]};v.validate_source_index(rows,index)
        # Mutate only the review-only proof, so evidence validation cannot be
        # what rejects these source-time and eligibility mismatches.
        for key,value in (('source_utc','2026-09-10T12:59:59Z'),('seed_backfill',True),
                          ('review_holds',['held']),('source_utc',None)):
            changed=copy.deepcopy(index);changed['rows'][-1][key]=value
            with self.subTest(key=key),self.assertRaises(v.InvalidCorpus):v.validate_source_index(rows,changed)
        changed=copy.deepcopy(index);changed['rows'][-1]['name_screen']['status']='pending'
        with self.assertRaises(v.InvalidCorpus):v.validate_source_index(rows,changed)
        duplicate=copy.deepcopy(proof);duplicate['source_row_id']='clock-proof-copy';index['rows'].append(duplicate)
        with self.assertRaisesRegex(v.InvalidCorpus,'ambiguous'):v.validate_source_index(rows,index)

    def test_clock_label_cannot_be_its_own_decision_proof(self):
        p=clock_pair();p['review']['decision_claim_id']=p['review']['label_source_claim_id']
        with self.assertRaisesRegex(v.InvalidCorpus,'label'):v.validate_pair(p,4000)

    def test_clock_proof_groups_across_roles_and_splits(self):
        train,held=splits();held[0]['review']['decision_claim_id']=train[0]['review']['label_source_claim_id']
        with self.assertRaisesRegex(v.InvalidCorpus,'overlap'):v.validate_split(train,held,CUT,4000)

    def test_source_bound_clock_keeps_exact_freeze_semantics(self):
        train,held=splits()
        train[0]['recorded_at']='2026-09-30T23:59:59Z'
        train[0]['evidence'][0]['recorded_at']=train[0]['recorded_at']
        for p in held:
            p['recorded_at']='2026-10-01T00:00:01Z';p['evidence'][0]['recorded_at']=p['recorded_at']
        v.validate_split(train,held,CUT,4000)
        v.validate_source_index({'train':train,'heldout':held},fixture_source_index(train+held))
        train[0]['recorded_at']='2026-10-01T00:00:01Z'
        with self.assertRaisesRegex(v.InvalidCorpus,'held-out event'):v.validate_split(train,held,CUT,4000)

    def test_event_date_basis_seed_refused_even_when_label_is_seed(self):
        p,index=day_case();index['rows'][1]['seed_backfill']=True
        rows={'train':[p],'heldout':[]};v.validate_source_index(rows,index)
        # Use the label itself as basis: it passes the names/time gates but is a seed.
        cid=p['review']['label_source_claim_id'];p['review']['event_date_claim_ids']=[cid]
        index['rows'][1]['decision_day_review']['claim_ids']=[cid]
        with self.assertRaisesRegex(v.InvalidCorpus,'seed'):v.validate_source_index(rows,index)

    def test_event_date_cannot_follow_label_filing(self):
        p,index=day_case();rows={'train':[p],'heldout':[]}
        index['rows'][1]['source_utc']='2026-09-10T04:00:00Z';v.validate_source_index(rows,index)
        index['rows'][1]['source_utc']='2026-09-10T03:59:59Z'
        with self.assertRaisesRegex(v.InvalidCorpus,'event date.*filing'):v.validate_source_index(rows,index)

if __name__=='__main__':unittest.main()
