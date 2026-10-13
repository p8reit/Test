"""Conservative research sizing. No model confidence is fabricated."""
from decimal import Decimal as D
from math import floor

def screen(snapshot, settings, now):
    capital = D(str(settings['capital']))
    fee = D(str(settings['sell_fee_pct'])) / 100
    fixed = D(str(settings['contract_fee'])) + D(str(settings['hauling_cost']))
    location = int(settings['buy_location'])
    sell_location = int(settings['sell_location'])
    age = now - snapshot['timestamp']
    reasons = ['Contract sell-through has not been calibrated against completed sales.']
    if not settings.get('route_confirmed'):
        reasons.append('Confirm the buying location and actual fees; Jita 4-4 is only the initial reference.')
    if age > 900:
        reasons.append('Snapshot is older than 15 minutes.')
    candidates = []
    if age <= 900:
        for type_id, name in snapshot['names'].items():
            orders = sorted([o for o in snapshot['orders'] if str(o['type_id']) == str(type_id)
                             and not o['is_buy_order'] and o['location_id'] == location], key=lambda o:o['price'])
            contracts = [c for c in snapshot['contracts'] if str(c['type_id']) == str(type_id)
                         and c['location_id'] == sell_location and c['quantity'] > 0]
            if not orders or not contracts:
                continue
            # Comparable ASK prices are hypotheses, never completed-sale evidence.
            ask = min(D(str(c['price'])) / c['quantity'] for c in contracts)
            target = ask * D('0.999')
            budget = capital / 2
            quantity, cost, ceiling = 0, D(0), D(0)
            for order in orders:
                price = D(str(order['price']))
                if price >= target * (1-fee):
                    break
                count = min(int(order['volume_remain']), max(0, floor((budget-fixed-cost)/price)))
                if count <= 0:
                    break
                quantity += count
                cost += price * count
                ceiling = price
            if not quantity:
                continue
            profit = quantity * target * (1-fee) - cost - fixed
            if profit <= 0:
                continue
            candidates.append(dict(type_id=int(type_id), name=name, quantity=quantity,
                buy_ceiling=float(ceiling), buy_average=float(cost/quantity), buy_cost=float(cost),
                sell_target=float(target), bundle_total=float(target*quantity),
                profit_if_all_sold=float(profit), full_capital_return_pct=float(profit/capital*100),
                comparable_contracts=len(contracts), status='Research only',
                warning='Sizing reflects acquisition depth, not proven daily contract demand. One hypothetical bundle; fees must match that bundle.'))
    candidates.sort(key=lambda c:c['profit_if_all_sold'], reverse=True)
    return dict(recommendations=[], decision='No qualifying trade', blockers=reasons,
                research=candidates[:2], timestamp=snapshot['timestamp'], source=snapshot['source'],
                target_profit=float(capital*D(str(settings['target_pct']))/100),
                confidence='Uncalibrated', age_seconds=max(0, int(age)))
