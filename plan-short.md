## Data Collection
Fetch closed 2024-2025 events from gamma.polymarket.com/events (volume > $100k)
Filter top 5 events with duration ≥ 6 months by volume
Extract event_id, title, start_date, end_date

## Market Analysis
For each event, fetch markets (bets) from /events/{id}
Filter markets with ≥5% of total event volume (reduce noise)
Extract token_id for each major market

## Price History
Fetch 60-second price data via clob.polymarket.com/prices-history
Iterate in weekly chunks (API limitation)
Aggregate to hourly averages for visualization

## Visualization
Plot all major candidates on single chart (Trump, Kamala, etc.)
Save data to JSON for reuse

## News Correlation (GDELT)
Query GDELT Doc API for event-related articles
Aggregate daily article counts
Correlate news volume with price volatility
(Note: GDELT Doc API lacks per-article sentiment)
