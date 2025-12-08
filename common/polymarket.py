import json
from uuid import uuid4
from pathlib import Path
from datetime import timedelta

import requests
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).parent.parent / 'data'


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
    
    # Calculate total number of chunks for progress bar
    total_days = (end_date - start_date).days
    total_chunks = (total_days + 6) // 7  # Round up
    
    with tqdm(total=total_chunks, desc="Fetching price history", unit="chunk") as pbar:
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
            
            history = r.json().get('history', [])
            for point in history:
                times.append(pd.to_datetime(point['t'], unit='s'))
                prices.append(float(point['p']))
            
            pbar.update(1)
            pbar.set_postfix({'points': len(times)})
            current = chunk_end
    
    return {'times': times, 'prices': prices}


def load_market_data(filename: str) -> dict:
    filepath = DATA_DIR / filename

    with open(filepath) as f:
        data = json.load(f)

    data['event']['start_date'] = pd.to_datetime(data['event']['start_date'])
    data['event']['end_date'] = pd.to_datetime(data['event']['end_date'])

    # Single-market format: price_data has 'times' and 'prices' directly
    times_raw = data['price_data']['times']
    data['price_data']['times'] = [
        pd.to_datetime(t) for t in tqdm(times_raw, desc="Loading times", unit="point")
    ]

    return data


def load_single_market_data(
    event_id: int,
    token_id: str,
    show_plot: bool = False,
) -> dict:
    event = fetch_event(event_id)
    start_date = pd.to_datetime(event['startDate'], utc=True)
    end_date = pd.to_datetime(event['endDate'], utc=True)

    # Find market info by token_id
    market_info = None
    for market in event['markets']:
        token_ids = json.loads(market['clobTokenIds'])
        if token_id in token_ids:
            market_info = {
                'question': market['question'],
                'volume': float(market.get('volume', 0)),
                'token_id': token_id,
            }
            break

    if market_info is None:
        raise ValueError(f"Token {token_id} not found in event {event_id}")

    price_data = fetch_price_history(token_id, start_date, end_date)
    print(f"Loaded {len(price_data['times']):,} price points for: {market_info['question'][:50]}")

    if show_plot:
        df = pd.DataFrame({'time': price_data['times'], 'price': price_data['prices']})
        df['hour'] = df['time'].dt.floor('h')
        hourly = df.groupby('hour')['price'].mean()

        plt.figure(figsize=(14, 6))
        plt.plot(hourly.index, hourly.values, linewidth=2, color='darkblue')
        plt.xlabel('Date')
        plt.ylabel('Probability')
        plt.title(f"{event['title']}\n{market_info['question']}")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.show()

    return {
        'event': {
            'id': event_id,
            'title': event['title'],
            'slug': event['slug'],
            'start_date': start_date,
            'end_date': end_date,
        },
        'market': market_info,
        'price_data': price_data,
    }


def save_market_data(data: dict, filename: str | None = None) -> Path:
    DATA_DIR.mkdir(exist_ok=True)

    if filename is None:
        filename = f"{data['event']['slug']}-{uuid4().hex[:5]}.json"

    filepath = DATA_DIR / filename

    times_iso = [
        t.isoformat()
        for t in tqdm(data['price_data']['times'], desc="Converting times to ISO", unit="point")
    ]

    to_save = {
        'event': {
            'id': data['event']['id'],
            'title': data['event']['title'],
            'slug': data['event']['slug'],
            'start_date': data['event']['start_date'].isoformat(),
            'end_date': data['event']['end_date'].isoformat(),
        },
        'market': data['market'],
        'price_data': {
            'times': times_iso,
            'prices': data['price_data']['prices'],
        },
    }

    with open(filepath, 'w') as f:
        json.dump(to_save, f, indent=2)

    print(f"Data saved to {filepath}")
    return filepath
