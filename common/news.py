import csv
from pathlib import Path
from datetime import timedelta

import requests
import pandas as pd
from tqdm import tqdm
from sentence_transformers import CrossEncoder

DATA_DIR = Path(__file__).parent.parent / 'data'

# Mapping: (event_id, short_name) -> keywords for news search
MARKET_KEYWORDS = {
    (903193, "kamala"): ["election", "Democrat", "Harris", "Kamala", "vice president"],
    (903193, "trump"): ["election", "Republican", "Trump", "Donald", "MAGA"],
    (13551, "ukraine"): ["Trump", "Ukraine", "war", "ceasefire", "peace", "negotiations", "Zelensky"],
    (21257, "israel"): ["Israel", "Hamas", "ceasefire", "Gaza", "war", "truce", "hostages"],
    (12641, "tiktok"): ["TikTok", "ByteDance", "China", "ban", "US", "regulation", "app"],
}

MAJOR_DOMAINS = [
    "nytimes.com",
    "washingtonpost.com",
    "cnn.com",
    "foxnews.com",
    "abcnews.go.com",
    "nbcnews.com",
    "cbsnews.com",
    "bloomberg.com",
    "reuters.com",
    "bbc.com",
    "theguardian.com",
]


def fetch_news_for_period(
    keywords: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    max_per_domain: int = 250,
) -> list[dict]:
    all_articles = []
    current = start_date
    week_delta = timedelta(days=7)

    total_weeks = ((end_date - start_date).days + 6) // 7
    total_requests = total_weeks * len(MAJOR_DOMAINS)

    with tqdm(total=total_requests, desc="Fetching news", unit="req") as pbar:
        while current < end_date:
            chunk_end = min(current + week_delta, end_date)
            start_str = current.strftime('%Y%m%d%H%M%S')
            end_str = chunk_end.strftime('%Y%m%d%H%M%S')

            for domain in MAJOR_DOMAINS:
                query = f"sourcelang:English AND domain:{domain} AND ({' OR '.join(keywords)})"

                params = {
                    'query': query,
                    'mode': 'ArtList',
                    'maxrecords': max_per_domain,
                    'format': 'json',
                    'startdatetime': start_str,
                    'enddatetime': end_str,
                }

                try:
                    r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=30)
                    if r.status_code == 200 and r.text.strip():
                        articles = r.json().get('articles', [])
                        for article in articles:
                            article['source_domain'] = domain
                        all_articles.extend(articles)
                except Exception as e:
                    print(f"Error fetching {domain}: {e}")

                pbar.update(1)
                pbar.set_postfix({'articles': len(all_articles)})

            current = chunk_end

    return all_articles


def filter_by_relevance(
    articles: list[dict],
    query: str,
    threshold: float = -4.5,
) -> list[dict]:
    if not articles:
        return []

    model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')

    pairs = [(query, a.get('title', '')) for a in articles]

    print(f"Scoring {len(pairs)} articles for relevance...")
    scores = model.predict(pairs, show_progress_bar=True)

    seen = {}
    for article, score in zip(articles, scores):
        if score >= threshold:
            article['relevance_score'] = float(score)
            title_key = article.get('title', '').strip().lower()
            if title_key not in seen or score > seen[title_key]['relevance_score']:
                seen[title_key] = article

    filtered = list(seen.values())
    print(f"Filtered to {len(filtered)} relevant articles (threshold={threshold})")
    return filtered


def save_news_to_csv(articles: list[dict], filename: str) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    filepath = DATA_DIR / filename

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'title', 'domain', 'relevance_score'])
        writer.writeheader()

        for article in tqdm(articles, desc="Saving to CSV", unit="row"):
            writer.writerow({
                'date': article.get('seendate', ''),
                'title': article.get('title', ''),
                'domain': article.get('source_domain', ''),
                'relevance_score': article.get('relevance_score', ''),
            })

    print(f"Saved {len(articles)} articles to {filepath}")
    return filepath
