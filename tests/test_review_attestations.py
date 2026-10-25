"""Synthetic proposal/attester and referential-stakes admission checks."""
import copy
import unittest
from test_temporal_sources import timed,index_for
from ember import validation as v


def review_case():
    p=timed(precision='day');index=index_for(p)
    basis=copy.deepcopy(index['rows'][0]);basis.update(source_row_id='fixture-date-row',claim_id='fixture-event-date')
    index['rows'].append(basis);index['attesting_seat']='fixture-attester'
    label=index['rows'][1]
    label['decision_day_review']={'status':'attested','proposed_by':'fixture-author','source_row_id':label['source_row_id'],
        'record_sha256':label['record_sha256'],'event_date':p['review']['event_date'],'claim_ids':p['review']['event_date_claim_ids'],
        'reader':'fixture-attester','receipt':'fixture-attestation'}
    return p,index


class ReviewAttestationTests(unittest.TestCase):
    def test_index_requires_body_screen_version(self):
        p,index=review_case();index.pop('stakes_screen_version',None)
        with self.assertRaises(v.InvalidCorpus):v.validate_source_index({'train':[p]},index)

    def test_proposal_has_author_but_cannot_claim_reader(self):
        _,index=review_case();proposal=index['rows'][1]['decision_day_review'];proposal['status']='proposed'
        proposal.pop('reader');proposal.pop('receipt')
        v.validate_schema('date_review',proposal)
        proposal['reader']='fixture-attester'
        with self.assertRaises(v.InvalidCorpus):v.validate_schema('date_review',proposal)

    def test_attested_reader_must_match_index_attester(self):
        p,index=review_case();v.validate_source_index({'train':[p]},index)
        for reader in ('another-seat','fixture-attester ',''):
            changed=copy.deepcopy(index);changed['rows'][1]['decision_day_review']['reader']=reader
            with self.subTest(reader=reader),self.assertRaises(v.InvalidCorpus):v.validate_source_index({'train':[p]},changed)

    def test_proposed_and_legacy_reviews_never_admitted(self):
        p,index=review_case()
        for mode in ('proposed','legacy'):
            changed=copy.deepcopy(index);review=changed['rows'][1]['decision_day_review']
            if mode=='proposed':review['status']='proposed';review.pop('reader');review.pop('receipt')
            else:review.pop('status');review.pop('proposed_by')
            with self.subTest(mode=mode),self.assertRaises(v.InvalidCorpus):v.validate_source_index({'train':[p]},changed)

    def test_attestation_source_binding(self):
        p,index=review_case()
        for key,value in (('record_sha256','1'*64),('source_row_id','different-row')):
            changed=copy.deepcopy(index);changed['rows'][1]['decision_day_review'][key]=value
            with self.subTest(key=key),self.assertRaises(v.InvalidCorpus):v.validate_source_index({'train':[p]},changed)
        index.pop('attesting_seat')
        with self.assertRaises(v.InvalidCorpus):v.validate_source_index({'train':[p]},index)

    def test_stakes_ignores_clear_flags(self):
        from ember.stakes import stakes_signals
        for text in ('The protected drawer needs consent before opening.',
                     'Four designated records require coupled stakes.',
                     'The sealed witness ledger is implicated.',
                     'A protected-family disclosure is at issue.'):
            with self.subTest(text=text):self.assertTrue(stakes_signals({'content':text,'protected':False,'coupled':False}))
        self.assertEqual(stakes_signals({'content':'A fixture about ordinary index performance.','protected':False}),[])

if __name__=='__main__':unittest.main()
