import json, sqlite3, time, unittest, tempfile
from unittest.mock import patch
from esi import ESI

class Response:
    def __init__(self):self.headers={'X-Pages':'2'}
    def read(self):return b'[{"type_id": 1}]'
    def __enter__(self):return self
    def __exit__(self,*args):pass

class ESITests(unittest.TestCase):
    def test_pagination_and_cache(self):
        client=ESI(sqlite3.connect(':memory:'))
        with patch('esi.urlopen',return_value=Response()) as http:
            self.assertEqual(len(client.pages('markets/10000002/orders/')),2)
            self.assertEqual(http.call_count,2)
            client.pages('markets/10000002/orders/')
            self.assertEqual(http.call_count,2)
    def test_parallel_file_pagination(self):
        with tempfile.TemporaryDirectory() as directory:
            con=sqlite3.connect(directory+'/cache.sqlite');client=ESI(con)
            response=Response();response.headers={'X-Pages':'3'}
            with patch('esi.urlopen',return_value=response) as http:
                self.assertEqual(len(client.pages('example/')),3)
                self.assertEqual(http.call_count,3)
                self.assertEqual(con.execute('SELECT count(*) FROM cache').fetchone()[0],3)
            con.close()
    def test_cached_age_is_preserved(self):
        con=sqlite3.connect(':memory:');client=ESI(con)
        url='https://esi.evetech.net/latest/example/'
        old=time.time()-1000
        con.execute('INSERT INTO cache VALUES (?,?,?,?,?)',(url,time.time()+100,'[]',1,old))
        client.get('example/')
        self.assertEqual(client.oldest_fetch,old)
    def test_wanted_singleton_expired_and_other_location_rejected(self):
        class Fake(ESI):
            def __init__(self):self.oldest_fetch=time.time()
            def pages(self,path):
                if path.startswith('markets'):return [dict(type_id=1,location_id=7,is_buy_order=False)]
                if path.startswith('contracts/public/items'):return [dict(type_id=1,quantity=5,is_included=True,is_singleton=True)]
                return [dict(contract_id=1,type='item_exchange',start_location_id=8,price=100,date_expired='2099-01-01T00:00:00Z'),dict(contract_id=2,type='item_exchange',start_location_id=8,price=100,date_expired='2000-01-01T00:00:00Z')]
        self.assertEqual(Fake().collect(7,8)['contracts'],[])
