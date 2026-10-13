"""Read-only ESI client with persisted HTTP cache and complete pagination."""
import json, time, sqlite3
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from email.utils import parsedate_to_datetime

class ESI:
    def __init__(self, db):
        self.db = db
        self.oldest_fetch = time.time()
        self.db.execute('CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, expires REAL, body TEXT, pages INTEGER, fetched REAL)')
    def get(self, path, page=None):
        url = 'https://esi.evetech.net/latest/' + path + ('?page='+str(page) if page else '')
        row = self.db.execute('SELECT expires,body,pages,fetched FROM cache WHERE url=?',(url,)).fetchone()
        if row and row[0] > time.time():
            self.oldest_fetch = min(self.oldest_fetch, row[3])
            return json.loads(row[1]), row[2]
        for attempt in range(3):
            try:
                with urlopen(Request(url,headers={'User-Agent':'JitaLedger/0.1 (personal research tool)','Accept':'application/json'}), timeout=25) as r:
                    body = r.read().decode()
                    pages = int(r.headers.get('X-Pages','1'))
                    expires = parsedate_to_datetime(r.headers['Expires']).timestamp() if r.headers.get('Expires') else time.time()+60
                    remaining = int(r.headers.get('X-Esi-Error-Limit-Remain','100'))
                self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?)',(url,expires,body,pages,time.time()))
                self.db.commit()
                if remaining < 10:
                    raise RuntimeError('ESI error budget is low; wait before refreshing.')
                return json.loads(body), pages
            except HTTPError as e:
                if e.code not in (429,500,502,503,504) or attempt == 2:
                    raise RuntimeError(f'ESI request failed: HTTP {e.code} for {path}') from e
                delay = min(30, max(1, int(e.headers.get('Retry-After','2'))))
                time.sleep(delay)
        raise RuntimeError('ESI retries exhausted')
    def pages(self,path):
        first, count = self.get(path,1)
        result = list(first)
        filename = self.db.execute('PRAGMA database_list').fetchone()[2]
        if filename and count>2:
            def fetch_page(page):
                with sqlite3.connect(filename,timeout=30) as con:
                    client=ESI(con)
                    body,_=client.get(path,page)
                    return body,client.oldest_fetch
            # Four concurrent reads bound load while avoiding hundreds of serial round trips.
            with ThreadPoolExecutor(max_workers=4) as pool:
                for body,age in pool.map(fetch_page,range(2,count+1)):
                    result.extend(body)
                    self.oldest_fetch=min(self.oldest_fetch,age)
        else:
            for p in range(2,count+1):
                result.extend(self.get(path,p)[0])
        return result
    def collect(self, buy_location, sell_location):
        started = time.time()
        self.oldest_fetch = started
        orders = [o for o in self.pages('markets/10000002/orders/') if o['location_id']==buy_location and not o['is_buy_order']]
        types = {o['type_id'] for o in orders}
        listings = self.pages('contracts/public/10000002/')
        listings.sort(key=lambda c:c.get('date_issued',''),reverse=True)
        contracts = []
        checked = 0
        for c in listings:
            if c['type'] != 'item_exchange' or c['start_location_id'] != sell_location or c.get('price',0)<=0:
                continue
            if c.get('date_expired','') <= time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()):
                continue
            checked += 1
            # Bounded scan explicitly reported; never claim a complete universe scan.
            if checked > 150:
                break
            items = self.pages(f"contracts/public/items/{c['contract_id']}/")
            if len(items)!=1:
                continue
            item = items[0]
            if not item.get('is_included') or item.get('is_singleton',False) or item.get('is_blueprint_copy',False) or item.get('raw_quantity',0)<0 or item['type_id'] not in types:
                continue
            contracts.append(dict(type_id=item['type_id'],quantity=item['quantity'],price=c['price'],location_id=c['start_location_id'],contract_id=c['contract_id']))
        names = {}
        safe_types = set()
        for tid in {c['type_id'] for c in contracts}:
            details = self.get(f'universe/types/{tid}/')[0]
            group = self.get(f"universe/groups/{details['group_id']}/")[0]
            # Public item payloads do not expose a reliable packaged flag.
            # Restrict discovery to commodity categories without fitted/assembled ships.
            if group['category_id'] in {4,5,8,17,20,42,43}:
                names[str(tid)] = details['name']
                safe_types.add(tid)
        return dict(source='Live ESI • up to 150 eligible contract item lookups',timestamp=min(started,self.oldest_fetch),scanned_orders=len(orders),orders=[o for o in orders if o['type_id'] in safe_types],contracts=[c for c in contracts if c['type_id'] in safe_types],names=names)
