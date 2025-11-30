import json
from datetime import timedelta

import requests
import pandas as pd
from tqdm import tqdm


def fetch_event(event_id: int) -> dict:
    r = requests.get(f"https://gamma-api.polymarket.com/events/{event_id}")
    return r.json()


def filter_markets_by_volume(event: dict, threshold_pct: float = 0.05) -> list[dict]:
    total_volume = sum(float(m.get('volume', 0)) for m in event['markets'])
    threshold = total_volume * threshold_pct
    
    filtered = []
    for market in event['markets']:
        vol = float(market.get('volume', 0))
        if vol >= threshold:
            filtered.append({
                'question': market['question'],
                'volume': vol,
                'token_id': json.loads(market['clobTokenIds'])[0]
            })
    
    return filtered


def fetch_price_history(token_id: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> dict:
    times = []
    prices = []
    current = start_date
    
    while current < end_date:
        chunk_end = min(current + timedelta(days=7), end_date)
        
        r = requests.get(
            "https://clob.polymarket.com/prices-history",
            params={
                "market": token_id,
                "startTs": int(current.timestamp()),
                "endTs": int(chunk_end.timestamp())
            }
        )
        
        for point in r.json()['history']:
            times.append(pd.to_datetime(point['t'], unit='s'))
            prices.append(float(point['p']))
        
        current = chunk_end
    
    return {'times': times, 'prices': prices}


def load_market_data(filename: str) -> dict:
    from pathlib import Path

    data_dir = Path(__file__).parent.parent / 'data'
    filepath = data_dir / filename

    with open(filepath) as f:
        data = json.load(f)

    data['event']['start_date'] = pd.to_datetime(data['event']['start_date'])
    data['event']['end_date'] = pd.to_datetime(data['event']['end_date'])

    for question, series in tqdm(data['price_data'].items(), desc="Loading price series"):
        series['times'] = [pd.to_datetime(t) for t in series['times']]

    return data
