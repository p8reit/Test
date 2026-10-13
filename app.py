import argparse, json, sqlite3, time, threading, math
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from engine import screen
from esi import ESI

ROOT = Path(__file__).parent
DATA = ROOT / '.data'
DATA.mkdir(exist_ok=True)
LOCK = threading.Lock()
DEFAULTS = dict(capital=50_000_000_000,target_pct=1,buy_location=60003760,sell_location=60003760,sell_fee_pct=1,contract_fee=10000,hauling_cost=0,route_confirmed=False)

def db():
    con = sqlite3.connect(DATA/'ledger.sqlite')
    con.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, body TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, timestamp REAL, body TEXT)')
    return con

def read(key, default=None):
    with db() as con:
        row=con.execute('SELECT body FROM state WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

def save(key,value):
    with db() as con:
        con.execute('INSERT OR REPLACE INTO state VALUES (?,?)',(key,json.dumps(value)))
        if key=='snapshot' and value.get('source','').startswith('Live ESI'):
            con.execute('INSERT INTO snapshots(timestamp,body) VALUES (?,?)',(value['timestamp'],json.dumps(value)))
            con.execute('DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT 30)')

def demo():
    specs=[(40520,'Large Skill Injector',800_000_000,825_000_000,100),(44992,'PLEX',5_000_000,5_200_000,20000),(40519,'Skill Extractor',450_000_000,465_000_000,200),(34,'Tritanium',4,4.3,100000000)]
    return dict(source='DEMO • synthetic prices, not trading advice',timestamp=time.time(),
        names={str(t):n for t,n,b,s,q in specs},
        orders=[dict(type_id=t,price=b,volume_remain=q,location_id=60003760,is_buy_order=False) for t,n,b,s,q in specs],
        contracts=[dict(type_id=t,price=s*10,quantity=10,location_id=60003760) for t,n,b,s,q in specs])

def validate(s):
    if set(s)!=set(DEFAULTS): raise ValueError('All settings fields are required.')
    for key in DEFAULTS:
        if key=='route_confirmed':
            if type(s[key]) is not bool: raise ValueError('Confirmation must be boolean.')
        elif type(s[key]) not in (int,float) or not math.isfinite(s[key]) or s[key]<0:
            raise ValueError(f'Invalid {key}')
    if s['capital']<=0 or not 0<s['target_pct']<=100 or s['sell_fee_pct']>=100:
        raise ValueError('Capital, return target, or fees are invalid.')
    for key in ('buy_location','sell_location'):
        if s[key]<=0 or int(s[key])!=s[key]: raise ValueError('Location IDs must be positive integers.')
    return s

class Handler(BaseHTTPRequestHandler):
    def send(self,body,status=200,kind='application/json'):
        data=body.encode() if isinstance(body,str) else json.dumps(body).encode()
        try:
            self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data))); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):
            pass  # A disconnected browser does not invalidate a completed refresh.
    def do_GET(self):
        if self.path=='/api/state':
            settings=read('settings',DEFAULTS); snapshot=read('snapshot')
            result=screen(snapshot,settings,time.time()) if snapshot else dict(decision='No data collected',recommendations=[],research=[],blockers=['Refresh live ESI or load the labeled demo.'])
            return self.send(dict(settings=settings,result=result,journal=read('journal',[])))
        if self.path=='/': return self.send((ROOT/'static/index.html').read_text(),kind='text/html; charset=utf-8')
        return self.send({'error':'Not found'},404)
    def do_POST(self):
        # Local-only prototype; reject cross-site form/JSON requests.
        if self.headers.get('Origin') and self.headers['Origin'] != 'http://'+self.headers.get('Host',''):
            return self.send({'error':'Cross-origin request rejected'},403)
        if self.headers.get('Content-Type','')!='application/json': return self.send({'error':'JSON required'},415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>8192: raise ValueError('Request too large')
            body=json.loads(self.rfile.read(length))
            if self.path=='/api/settings': save('settings',validate(body))
            elif self.path=='/api/journal':
                required={'item','quantity','buy_total','sell_total','fees','hours'}
                if set(body)!=required or not isinstance(body['item'],str) or not body['item'].strip() or len(body['item'])>150: raise ValueError('Invalid journal entry')
                for key in required-{'item'}:
                    if type(body[key]) not in (int,float) or not math.isfinite(body[key]) or body[key]<0: raise ValueError('Invalid journal number')
                if body['quantity']<=0 or int(body['quantity'])!=body['quantity'] or body['buy_total']<=0: raise ValueError('Quantity and acquisition total must be positive')
                body['net_profit']=body['sell_total']-body['buy_total']-body['fees']
                body['recorded_at']=time.time()
                with LOCK:
                    journal=read('journal',[]); journal.append(body); save('journal',journal)
            elif self.path=='/api/demo': save('snapshot',demo())
            elif self.path=='/api/refresh':
                if not LOCK.acquire(False): return self.send({'error':'Refresh already running'},409)
                try:
                    s=read('settings',DEFAULTS)
                    with db() as con: snapshot=ESI(con).collect(int(s['buy_location']),int(s['sell_location']))
                    save('snapshot',snapshot)
                finally: LOCK.release()
            else: return self.send({'error':'Not found'},404)
            self.send({'ok':True})
        except (ValueError,RuntimeError,OSError,KeyError) as e:
            self.send({'error':str(e)},400)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8000); args=parser.parse_args()
    print(f'Jita Ledger listening on local port {args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
