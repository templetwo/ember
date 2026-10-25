"""Synthetic clock decision provenance must not disclose the act to the model."""
import copy
import unittest
from test_p0 import pair, fixture_source_index
from ember import validation as v


class ClockEvidenceLeakTests(unittest.TestCase):
    def test_decision_record_is_not_evidence_even_with_normalized_alias(self):
        for transform in (lambda s:s,lambda s:' \t'+s.upper()+'\n'):
            p=pair(1,'PAUSE');p['review']['decision_claim_id']=transform(p['evidence'][0]['claim_id'])
            with self.subTest(transform=transform),self.assertRaisesRegex(v.InvalidCorpus,'clock decision'):
                v.validate_pair(p,4000)

    def test_clock_proof_is_review_only_but_still_binds_the_decision(self):
        p=pair(1,'PAUSE');p['review']['decision_claim_id']='fixture-separate-clock'
        index=fixture_source_index([p])
        # This also works against the old fixture helper during the red run.
        if not any(r['claim_id']=='fixture-separate-clock' for r in index['rows']):
            proof=copy.deepcopy(index['rows'][0]);proof.update(source_row_id='separate-clock-row',claim_id='fixture-separate-clock')
            index['rows'].append(proof)
        v.validate_pair(p,4000);v.validate_source_index({'train':[p],'heldout':[]},index)
        self.assertNotIn('fixture-separate-clock',v.render_evidence(p['evidence']))
        self.assertIn('fixture-separate-clock',v.linked_claim_ids(p))

    def test_clock_proof_id_cannot_leak_through_model_facing_text(self):
        for field in ('situation','evidence','rationale','source_claim_ids','cited_claim_ids'):
            for token in ('c'*64,'C'*12,'cc cc cc cc cc cc'):
                p=pair(1,'PAUSE');p['review']['decision_claim_id']='c'*64
                if field=='evidence':p['evidence'][0]['text']+=' '+token
                elif field=='rationale':p['target']['rationale']+=' '+token
                elif field=='source_claim_ids':p[field].append(token)
                elif field=='cited_claim_ids':p['target'][field].append(token)
                else:p[field]+=' '+token
                with self.subTest(field=field,token=token),self.assertRaisesRegex(v.InvalidCorpus,'clock decision'):
                    v.validate_pair(p,4000)

if __name__=='__main__':unittest.main()
