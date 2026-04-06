import pandas as pd
from vnstock import Listing

try:
    l = Listing(source='VCI')
    inds = l.symbols_by_industries(to_df=True)
    print('VCI cols:', inds.columns.tolist() if not inds.empty else 'empty')
    if not inds.empty:
        if 'comGroupCode' in inds.columns:
            print('VCI Unique comGroupCode:', inds['comGroupCode'].unique().tolist())
        if 'exchange' in inds.columns:
            print('VCI Unique exchange:', inds['exchange'].unique().tolist())
except Exception as e:
    print('VCI error:', e)

try:
    l2 = Listing(source='KBS')
    inds2 = l2.all_symbols(to_df=True)
    print('KBS cols:', inds2.columns.tolist() if not inds2.empty else 'empty')
    if not inds2.empty:
        if 'exchange' in inds2.columns:
            print('KBS Unique exchange:', inds2['exchange'].unique().tolist())
except Exception as e:
    print('KBS error:', e)
