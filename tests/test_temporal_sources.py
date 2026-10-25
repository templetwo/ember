"""Synthetic timing, source-screen and grouping fixtures only."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ember import validation as v
from ember.validation import InvalidCorpus
from test_p0 import pair,splits,CUT,fixture_manifest


def timed(label='PAUSE',precision='clock'):
    p=pair(1,label,'2026-09-10T13:00:00Z');p['recorded_at_precision']=precision
    if precision!='clock':p['review'].pop('decision_claim_id')
    p['evidence'][0]['source_row_id']='fixture-row-1'
    p['review']['label_source_row_id']='fixture-label-row-1'
    if precision=='day':
        p['recorded_at']='2026-09-10T04:00:00Z'
        p['review']['event_date']='2026-09-10'
        p['review']['event_date_claim_ids']=['fixture-event-date']
    return p


def index_for(p):
    def item(rid,cid,stamp):
        return dict(source_row_id=rid,claim_id=cid,source_utc=stamp,record_sha256='0'*64,
                    timestamp_basis='explicit-source-offset',seed_backfill=False,review_holds=[],
                    name_screen={'status':'no-person-named','reader':'fixture-reviewer','receipt':'fixture-only','public_record_refs':[]})
    result = {'schema_version':'0.1','rows':[
        item(p['evidence'][0]['source_row_id'],p['evidence'][0]['claim_id'],p['evidence'][0]['recorded_at']),
        item(p['review']['label_source_row_id'],p['review']['label_source_claim_id'],'2026-09-11T00:00:00Z')]}
    if p['recorded_at_precision']=='clock':
        result['rows'].append(item('fixture-clock-row',p['review']['decision_claim_id'],p['recorded_at']))
    return result


class TemporalSourceTests(unittest.TestCase):
    def test_precision_is_required_without_clock_default(self):
        p=timed();del p['recorded_at_precision']
        with self.assertRaises(InvalidCorpus):v.validate_pair(p,4000)

    def test_day_floor_is_strict_and_midnight_eastern(self):
        p=timed(precision='day');p['evidence'][0]['recorded_at']='2026-09-09T23:59:59Z'
        v.validate_pair(p,4000)
        for stamp in ('2026-09-10T04:00:00Z','2026-09-10T04:00:01Z'):
            p['evidence'][0]['recorded_at']=stamp
            with self.assertRaisesRegex(InvalidCorpus,'day precision'):v.validate_pair(p,4000)
        p['evidence'][0]['recorded_at']='2026-09-09T00:00:00Z'
        for stamp in ('2026-09-10T00:00:00Z','2026-09-10T00:00:00-05:00'):
            p['recorded_at']=stamp
            with self.assertRaisesRegex(InvalidCorpus,'day precision'):v.validate_pair(p,4000)

    def test_clock_allows_evidence_at_decision_instant(self):
        v.validate_pair(timed(),4000)

    def test_eastern_floor_tracks_season_and_dst_transition(self):
        for day,hour in (('2026-02-07','05'),('2026-07-06','04'),
                         ('2026-03-08','05'),('2026-03-09','04'),
                         ('2026-11-01','04'),('2026-11-02','05')):
            with self.subTest(day=day):
                self.assertEqual(v.eastern_day_floor(day),v.timestamp(day+'T'+hour+':00:00Z'))

    def test_day_requires_reviewed_event_date_not_filing_date(self):
        p=timed(precision='day');index=index_for(p)
        rows={'train':[p],'heldout':[]}
        with self.assertRaisesRegex(InvalidCorpus,'event date'):v.validate_source_index(rows,index)
        basis=copy.deepcopy(index['rows'][0])
        basis.update(source_row_id='fixture-date-row',claim_id='fixture-event-date')
        index['rows'].append(basis)
        label=index['rows'][1]
        label['decision_day_review']={'event_date':'2026-09-10','claim_ids':['fixture-event-date'],
                                      'reader':'fixture-reader','receipt':'fixture-only'}
        # The later label filing date is deliberately different from the event date.
        v.validate_source_index(rows,index)
        for key,value in (('event_date','2026-09-11'),('claim_ids',['absent']),('receipt',' ')):
            changed=copy.deepcopy(index);changed['rows'][1]['decision_day_review'][key]=value
            with self.subTest(key=key),self.assertRaises(InvalidCorpus):v.validate_source_index(rows,changed)
        index['rows'].append(copy.deepcopy(basis));index['rows'][-1]['source_row_id']='second-date-row'
        with self.assertRaisesRegex(InvalidCorpus,'ambiguous'):v.validate_source_index(rows,index)

    def test_bounding_claims_bind_resolved_times_and_eligibility(self):
        p=timed(precision='bounded-by-records');index=index_for(p)
        p['review']['decision_time_bounds']={'start_claim_id':'fixture-bound-start',
            'end_claim_id':'fixture-bound-end','end_at':'2026-09-10T13:10:00Z'}
        for cid,stamp in (('fixture-bound-start',p['recorded_at']),('fixture-bound-end','2026-09-10T13:10:00Z')):
            item=copy.deepcopy(index['rows'][0]);item.update(source_row_id=cid,claim_id=cid,source_utc=stamp)
            index['rows'].append(item)
        rows={'train':[p],'heldout':[]};v.validate_source_index(rows,index)
        for key,value in (('source_utc','2026-09-09T00:00:00Z'),('seed_backfill',True),('review_holds',['held'])):
            changed=copy.deepcopy(index);changed['rows'][2][key]=value
            with self.subTest(key=key),self.assertRaises(InvalidCorpus):v.validate_source_index(rows,changed)

    def test_source_index_change_needs_new_release_review(self):
        with tempfile.TemporaryDirectory() as folder:
            path,manifest=fixture_manifest(Path(folder));v.load_manifest(path)
            source=Path(folder)/manifest['source_index']['path']
            source.write_bytes(source.read_bytes()+b'\n')
            with self.assertRaisesRegex(InvalidCorpus,'hash mismatch'):v.load_manifest(path)
            manifest['source_index']['sha256']=v.digest(source.read_bytes())
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(InvalidCorpus,'release receipt'):v.load_manifest(path)

    def test_bounded_window_needs_receipts_and_valid_upper_endpoint(self):
        p=timed(precision='bounded-by-records')
        with self.assertRaises(InvalidCorpus):v.validate_pair(p,4000)
        p['review']['decision_time_bounds']={'start_claim_id':'fixture-bound-start','end_claim_id':'fixture-bound-end','end_at':'2026-09-10T13:10:00Z'}
        v.validate_pair(p,4000)
        for stamp in ('2026-09-09T00:00:00Z','2026-09-10T13:00:00Z'):
            p['review']['decision_time_bounds']['end_at']=stamp
            with self.assertRaisesRegex(InvalidCorpus,'decision window'):v.validate_pair(p,4000)

    def test_day_rows_near_freeze_are_excluded_in_both_splits(self):
        for day in ('2026-09-29','2026-09-30','2026-10-01'):
            for split in (0,1):
                train,held=splits();p=(train,held)[split][0]
                p['recorded_at_precision']='day';p['recorded_at']=day+'T04:00:00Z';p['review'].pop('decision_claim_id')
                p['review']['event_date']=day;p['review']['event_date_claim_ids']=['fixture-date-'+p['pair_id']]
                p['evidence'][0]['recorded_at']='2026-08-01T00:00:00Z'
                with self.subTest(day=day,split=split),self.assertRaisesRegex(InvalidCorpus,'day precision.*freeze'):
                    v.validate_split(train,held,CUT,4000)

    def test_day_rows_two_days_away_are_admitted(self):
        train,held=splits()
        for rows,day in ((train,'2026-09-28'),(held,'2026-10-02')):
            for p in rows:
                p['recorded_at_precision']='day';p['recorded_at']=day+'T04:00:00Z';p['review'].pop('decision_claim_id')
                p['review']['event_date']=day;p['review']['event_date_claim_ids']=['fixture-date-'+p['pair_id']]
                p['evidence'][0]['recorded_at']='2026-08-01T00:00:00Z'
        v.validate_split(train,held,CUT,4000)

    def test_bounded_window_cannot_straddle_freeze(self):
        train,held=splits();p=train[0];p['recorded_at_precision']='bounded-by-records';p['review'].pop('decision_claim_id')
        p['review']['decision_time_bounds']={'start_claim_id':'fixture-bound-start','end_claim_id':'fixture-bound-end','end_at':'2026-10-02T00:00:00Z'}
        with self.assertRaisesRegex(InvalidCorpus,'decision window.*freeze'):v.validate_split(train,held,CUT,4000)

    def test_shared_evidence_and_bound_ids_cannot_cross_splits(self):
        train,held=splits();p=held[0]
        p['evidence'].append(copy.deepcopy(train[0]['evidence'][0]))
        with self.assertRaisesRegex(InvalidCorpus,'overlap'):v.validate_split(train,held,CUT,4000)
        train,held=splits();p=held[0];p['recorded_at_precision']='bounded-by-records';p['review'].pop('decision_claim_id')
        p['review']['decision_time_bounds']={'start_claim_id':train[0]['review']['label_source_claim_id'],'end_claim_id':'fixture-bound-end','end_at':'2026-10-02T00:00:00Z'}
        with self.assertRaisesRegex(InvalidCorpus,'overlap'):v.validate_split(train,held,CUT,4000)

    def test_metadata_index_binds_evidence_to_resolved_time_and_row(self):
        p=timed();index=index_for(p);v.validate_source_index({'train':[p],'heldout':[]},index)
        for key,value in (('source_utc',None),('source_utc','2026-09-09T00:00:00Z'),('claim_id','wrong'),('review_holds',['unresolved-vault-import'])):
            changed=copy.deepcopy(index);changed['rows'][0][key]=value
            with self.subTest(key=key),self.assertRaises(InvalidCorpus):v.validate_source_index({'train':[p],'heldout':[]},changed)

    def test_seed_backfill_is_never_evidence_but_may_supply_label(self):
        p=timed();index=index_for(p);index['rows'][1]['seed_backfill']=True
        v.validate_source_index({'train':[p],'heldout':[]},index)
        index['rows'][0]['seed_backfill']=True
        with self.assertRaisesRegex(InvalidCorpus,'seed'):v.validate_source_index({'train':[p],'heldout':[]},index)

    def test_missing_or_held_name_screen_is_never_clear(self):
        p=timed();index=index_for(p)
        for screen in (None,{'status':'pending'},{'status':'held','reader':'fixture','receipt':'fixture-only','public_record_refs':[]}):
            changed=copy.deepcopy(index);changed['rows'][0]['name_screen']=screen
            with self.subTest(screen=screen),self.assertRaises(InvalidCorpus):v.validate_source_index({'train':[p],'heldout':[]},changed)
        index['rows'][0]['name_screen']['status']='public-record-only'
        with self.assertRaises(InvalidCorpus):v.validate_source_index({'train':[p],'heldout':[]},index)
        index['rows'][0]['name_screen']['public_record_refs']=['https://example.invalid/synthetic-public-receipt']
        v.validate_source_index({'train':[p],'heldout':[]},index)

if __name__=='__main__':unittest.main()
