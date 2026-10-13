import unittest, time
from app import DEFAULTS, demo, validate
from engine import screen
from esi import ESI

class EngineTests(unittest.TestCase):
    def run_screen(self,snapshot=None,settings=None):
        return screen(snapshot or demo(),settings or DEFAULTS,time.time())
    def test_no_fabricated_recommendations(self):
        result=self.run_screen()
        self.assertEqual(result['recommendations'],[])
        self.assertTrue(result['research'])
        self.assertEqual(result['confidence'],'Uncalibrated')
    def test_fees_and_capital_constraints(self):
        s=demo();s['names']={'40520':'Injector'}
        r=self.run_screen(s)['research'][0]
        q=r['quantity']
        self.assertLessEqual(r['buy_cost']+DEFAULTS['contract_fee'],DEFAULTS['capital']/2)
        self.assertAlmostEqual(r['profit_if_all_sold'],q*r['sell_target']*.99-r['buy_cost']-10000,places=4)
    def test_stale_data_rejected(self):
        s=demo();s['timestamp']-=901
        self.assertEqual(self.run_screen(s)['research'],[])
    def test_fee_erases_spread(self):
        settings={**DEFAULTS,'sell_fee_pct':50}
        self.assertEqual(self.run_screen(settings=settings)['research'],[])
    def test_location_filter(self):
        settings={**DEFAULTS,'buy_location':123}
        self.assertEqual(self.run_screen(settings=settings)['research'],[])
    def test_two_items_max_and_shared_capital(self):
        r=self.run_screen()['research']
        self.assertLessEqual(len(r),2)
        self.assertLessEqual(sum(x['buy_cost']+10000 for x in r),DEFAULTS['capital'])
    def test_depth_weighted_cost(self):
        s=demo();s['names']={'40520':'Injector'};s['orders']=[dict(type_id=40520,price=800e6,volume_remain=2,location_id=60003760,is_buy_order=False),dict(type_id=40520,price=810e6,volume_remain=5,location_id=60003760,is_buy_order=False)]
        r=self.run_screen(s)['research'][0]
        self.assertEqual(r['quantity'],7)
        self.assertEqual(r['buy_cost'],2*800e6+5*810e6)
        self.assertEqual(r['buy_ceiling'],810e6)
    def test_invalid_settings(self):
        for change in ({'capital':0},{'sell_fee_pct':100},{'capital':float('nan')},{'buy_location':1.5},{'route_confirmed':'yes'}):
            with self.assertRaises(ValueError):validate({**DEFAULTS,**change})

class CollectionTests(unittest.TestCase):
    def test_reject_mixed_and_wanted_contracts(self):
        class Fake(ESI):
            def __init__(self):self.oldest_fetch=time.time()
            def pages(self,path):
                if path.startswith('markets'):return [dict(type_id=1,location_id=7,is_buy_order=False)]
                if path.startswith('contracts/public/items'):
                    cid=int(path.split('/')[-2]); item=dict(type_id=1,quantity=5,is_included=True)
                    return [item,item] if cid==2 else [{**item,'is_included':False}] if cid==3 else [item]
                return [dict(contract_id=i,type='item_exchange',start_location_id=8,price=100,date_expired='2099-01-01T00:00:00Z') for i in (1,2,3)]
            def get(self,path,page=None):return ({'category_id':17} if path.startswith('universe/groups') else {'name':'Test item','group_id':1}),1
        result=Fake().collect(7,8)
        self.assertEqual(len(result['contracts']),1)
        self.assertEqual(result['contracts'][0]['contract_id'],1)

if __name__=='__main__':unittest.main()
