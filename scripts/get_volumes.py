import json
import yfinance as yf
import pandas as pd
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    data_dir = os.path.join(root_dir, "data")
    json_path = os.path.join(data_dir, "lists.json")
    output_path = os.path.join(data_dir, "volumes.json")

    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    # Read lists.json
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract single tickers
    tickers = []
    for sector in data.values():
        if 'items' in sector:
            for item in sector['items']:
                if 'ticker' in item:
                    tickers.append(item['ticker'])

    # Get unique tickers
    tickers = list(set(tickers))
    print(f"Fetching volume for {len(tickers)} tickers. This might take a few seconds...")

    volumes = {}
    
    # Download data
    if tickers:
        # We download 1 year of data to calculate both current day volume and 1-year average
        df = yf.download(tickers, period="1y")
        
        if 'Volume' in df:
            vol_df = df['Volume']
            
            # yfinance returns a Series if only one ticker is requested, else a DataFrame
            if isinstance(vol_df, pd.Series):
                try:
                    s = vol_df.dropna()
                    if not s.empty:
                        volumes[tickers[0]] = {
                            "volume": int(s.iloc[-1]),
                            "avg_volume_1y": int(s.mean())
                        }
                    else:
                        volumes[tickers[0]] = None
                except Exception:
                    volumes[tickers[0]] = None
            else:
                for ticker in tickers:
                    try:
                        if ticker in vol_df.columns:
                            s = vol_df[ticker].dropna()
                            if not s.empty:
                                volumes[ticker] = {
                                    "volume": int(s.iloc[-1]),
                                    "avg_volume_1y": int(s.mean())
                                }
                            else:
                                volumes[ticker] = None
                        else:
                            volumes[ticker] = None
                    except Exception:
                        volumes[ticker] = None

    # Sort volumes dictionary: highest volume to lowest, putting Nones at the end
    # We use a default of -1 for sorting if volume is None
    sorted_volumes = dict(sorted(
        volumes.items(), 
        key=lambda item: item[1]["volume"] if item[1] is not None else -1, 
        reverse=True
    ))

    # Write the volumes back out to volumes.json
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_volumes, f, indent=4)

    print(f"Successfully processed {len(volumes)} tickers.")
    print(f"Volumes written to {output_path}")

if __name__ == "__main__":
    main()
