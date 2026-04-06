import pandas as pd
from vnstock import Listing

sources = ['VCI', 'KBS', 'DNSE', 'TCBS', 'SSI', 'VND']
for s in sources:
    try:
        df = Listing(source=s).all_symbols(to_df=True)
        if not df.empty:
            print(f"{s} cols: {df.columns.tolist()}")
            if 'exchange' in df.columns:
                print(f"  {s} exchange vals: {df['exchange'].unique().tolist()}")
            if 'comGroupCode' in df.columns:
                print(f"  {s} comGroupCode vals: {df['comGroupCode'].unique().tolist()}")
    except Exception as e:
        print(f"{s} err: {e}")
