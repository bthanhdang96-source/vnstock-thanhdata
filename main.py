import os
import json
import asyncio
import datetime
import pandas as pd
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from vnstock import Listing, Quote, Company

app = FastAPI(title="VNINDEX Local Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")

DATA_FILE = "cache_hose_data.json"
SYNC_STATUS = {
    "is_syncing": False,
    "progress": 0,
    "total": 0,
    "current_batch": 0,
    "total_batches": 0,
    "message": "Sẵn sàng"
}

HOSE_HISTORY_LENGTH = 260  # ~1 năm giao dịch

def load_cached_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def get_hose_symbols():
    """Lấy danh sách mã HOSE từ Listing API. Không dùng price_board()."""
    records = []
    try:
        from vnstock import Listing
        l = Listing(source='VCI')
        # Lấy danh sách HOSE
        hose_syms = l.symbols_by_group('HOSE')
        if hasattr(hose_syms, 'tolist'):
            hose_syms = set(hose_syms.tolist())
        else:
            hose_syms = set(hose_syms)

        inds = l.symbols_by_industries(to_df=True)
        if hasattr(inds, 'columns') and 'symbol' in inds.columns:
            hose_df = inds[inds['symbol'].isin(hose_syms)]
            records = hose_df.dropna(subset=['symbol']).to_dict('records')
            print(f"[VCI] Lay duoc {len(records)} ma HOSE.")
            return records
    except Exception as e:
        print("Loi VCI:", repr(e))

    try:
        from vnstock import Listing
        l_kbs = Listing(source='KBS')
        hose_syms = l_kbs.symbols_by_group('HOSE')
        if hasattr(hose_syms, 'tolist'):
            hose_syms = set(hose_syms.tolist())
        else:
            hose_syms = set(hose_syms)

        all_syms = l_kbs.all_symbols(to_df=True)
        if hasattr(all_syms, 'columns') and 'symbol' in all_syms.columns:
            hose_df = all_syms[all_syms['symbol'].isin(hose_syms)]
            records = hose_df.dropna(subset=['symbol']).to_dict('records')
            print(f"[KBS] Lay duoc {len(records)} ma HOSE.")
            return records
    except Exception as e:
        print("Loi KBS:", repr(e))
    return records

def safe_fetch_trading_stats(symbol):
    try:
        c = Company(source='VCI', symbol=symbol)
        stats = c.trading_stats()
        if not stats.empty:
            return {
                "pe": float(stats.get("pe", [0])[0]),
                "pb": float(stats.get("pb", [0])[0]),
                "avg_match_volume_2w": int(stats.get("avg_match_volume_2w", [0])[0])
            }
    except:
        pass
    return {"pe": 0, "pb": 0, "avg_match_volume_2w": 0}

def compute_rsi(series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=length, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(window=length, min_periods=1).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def compute_stoch(high, low, close, k=14, d=3):
    lowest_low = low.rolling(window=k, min_periods=1).min()
    highest_high = high.rolling(window=k, min_periods=1).max()
    stoch_k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    stoch_d = stoch_k.rolling(window=d, min_periods=1).mean()
    return stoch_k, stoch_d

def _pct(new_val, old_val):
    """Tính % thay đổi an toàn."""
    if old_val and old_val > 0:
        return float((new_val - old_val) / old_val * 100)
    return 0.0

def _avg_vol(df, start_idx, end_idx):
    """Trung bình volume trong khoảng [start_idx, end_idx] (tính từ cuối df)."""
    n = len(df)
    i_start = max(0, n - end_idx)
    i_end   = max(0, n - start_idx)
    chunk = df['volume'].iloc[i_start:i_end]
    return float(chunk.mean()) if len(chunk) > 0 else 0.0

def _sum_net_vol(df, n_periods):
    """Tổng volume ròng n phiên gần nhất. Net vol = vol × sign(price_change)."""
    tail = df.tail(n_periods)
    net = tail['volume'] * tail['price_dir']
    return float(net.sum())

def safe_fetch_quote_history(symbol):
    try:
        q = Quote(source='KBS', symbol=symbol)
        history_dir = "data/history"
        os.makedirs(history_dir, exist_ok=True)
        cache_file = os.path.join(history_dir, f"{symbol}.csv")
        
        df = pd.DataFrame()
        need_full_fetch = True
        
        if os.path.exists(cache_file):
            try:
                old_df = pd.read_csv(cache_file)
                if not old_df.empty and 'time' in old_df.columns:
                    old_df['time'] = pd.to_datetime(old_df['time'])
                    last_date = old_df['time'].max()
                    today = datetime.datetime.now()
                    start_str = last_date.strftime('%Y-%m-%d')
                    end_str = today.strftime('%Y-%m-%d')
                    
                    if start_str != end_str:
                        new_df = q.history(start=start_str, end=end_str, interval="1D", get_all=False)
                        if new_df is not None and not new_df.empty and 'time' in new_df.columns:
                            new_df['time'] = pd.to_datetime(new_df['time'])
                            df = pd.concat([old_df, new_df], ignore_index=True)
                        else:
                            df = old_df
                    else:
                        df = old_df
                        
                    need_full_fetch = False
            except Exception as e:
                print(f"Lỗi đọc cache csv cho {symbol}: {e}")
                
        if need_full_fetch:
            df = q.history(length=HOSE_HISTORY_LENGTH, interval="1D", get_all=False)

        if df is None or df.empty or len(df) < 50:
            return None

        # Clean duplicates mapping over appended segments
        df['time'] = pd.to_datetime(df['time'])
        df = df.drop_duplicates(subset=['time'], keep='last')
        df = df.sort_values(by='time').reset_index(drop=True)
        
        # Keep strictly HOSE_HISTORY_LENGTH
        df = df.tail(HOSE_HISTORY_LENGTH).reset_index(drop=True)
        
        # Save snapshot 
        df.to_csv(cache_file, index=False)

        for col in ['close', 'high', 'low', 'open', 'volume']:
            df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)

        # price direction cho net volume
        df['price_dir'] = df['close'].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

        # TA indicators
        df['RSI_14']              = compute_rsi(df['close'], 14)
        df['STOCHk_14'], df['STOCHd_14'] = compute_stoch(df['high'], df['low'], df['close'], 14, 3)
        df['SMA_50']              = df['close'].rolling(50, min_periods=1).mean()
        df['SMA_100']             = df['close'].rolling(100, min_periods=1).mean()

        n = len(df)
        last  = df.iloc[-1]
        prev1 = df.iloc[-2] if n > 1 else last

        close   = float(last['close'])
        volume  = float(last['volume'])

        # ---- Price % thay đổi theo kỳ ----
        def price_at(offset):
            idx = n - 1 - offset
            return float(df.iloc[idx]['close']) if idx >= 0 else close

        pct_1d = _pct(close, price_at(1))
        pct_1w = _pct(close, price_at(5))
        pct_1m = _pct(close, price_at(21))
        pct_1q = _pct(close, price_at(63))
        pct_1y = _pct(close, price_at(min(252, n - 1)))

        # ---- Volume % thay đổi theo kỳ ----
        avg_vol_today  = volume
        avg_vol_5d     = _avg_vol(df, 1, 6)      # 5 phiên gần nhất bỏ hôm nay
        avg_vol_5d_0   = _avg_vol(df, 6, 11)     # 5 phiên trước đó
        avg_vol_21d    = _avg_vol(df, 1, 22)
        avg_vol_21d_0  = _avg_vol(df, 22, 43)
        avg_vol_63d    = _avg_vol(df, 1, 64)
        avg_vol_63d_0  = _avg_vol(df, 64, 127)
        avg_vol_126d   = _avg_vol(df, 1, 127)    # nửa năm trước

        vol_pct_1d = _pct(volume, avg_vol_5d)           # hôm nay vs TB5 phiên gần
        vol_pct_1w = _pct(avg_vol_5d, avg_vol_5d_0)     # TB5 phiên vs TB5 phiên trước
        vol_pct_1m = _pct(avg_vol_21d, avg_vol_21d_0)
        vol_pct_1q = _pct(avg_vol_63d, avg_vol_63d_0)
        vol_pct_1y = _pct(volume, avg_vol_126d)          # hôm nay vs TB nửa năm

        # ---- Net volume ròng theo kỳ ----
        net_vol_1d = volume * float(last['price_dir'])
        net_vol_1w = _sum_net_vol(df, 5)
        net_vol_1m = _sum_net_vol(df, 21)
        net_vol_1q = _sum_net_vol(df, 63)
        net_vol_1y = _sum_net_vol(df, min(252, n))

        # MA Cross
        prev_ma50  = float(prev1['SMA_50'])
        prev_ma100 = float(prev1['SMA_100'])
        ma50       = float(last['SMA_50'])
        ma100      = float(last['SMA_100'])
        is_uptrend = bool((close > ma100) and (ma50 > ma100))

        def safe_f(v):
            return float(v) if pd.notnull(v) else 0.0

        return {
            # Realtime / latest
            "close":          close,
            "volume":         volume,
            "price_change":   float(close - float(prev1['close'])),
            "percent_change": pct_1d,

            # Price % by period
            "pct_1d": round(pct_1d, 3),
            "pct_1w": round(pct_1w, 3),
            "pct_1m": round(pct_1m, 3),
            "pct_1q": round(pct_1q, 3),
            "pct_1y": round(pct_1y, 3),

            # Volume % by period
            "vol_pct_1d": round(vol_pct_1d, 3),
            "vol_pct_1w": round(vol_pct_1w, 3),
            "vol_pct_1m": round(vol_pct_1m, 3),
            "vol_pct_1q": round(vol_pct_1q, 3),
            "vol_pct_1y": round(vol_pct_1y, 3),

            # Net volume by period
            "net_vol_1d": round(net_vol_1d, 0),
            "net_vol_1w": round(net_vol_1w, 0),
            "net_vol_1m": round(net_vol_1m, 0),
            "net_vol_1q": round(net_vol_1q, 0),
            "net_vol_1y": round(net_vol_1y, 0),

            # TA indicators
            "rsi":      safe_f(last['RSI_14']),
            "stoch_k":  safe_f(last['STOCHk_14']),
            "stoch_d":  safe_f(last['STOCHd_14']),
            "ma50":     safe_f(ma50),
            "ma100":    safe_f(ma100),
            "is_uptrend": is_uptrend,
        }
    except Exception as e:
        print(f"  [ERR] {symbol}: {repr(e)}")
        return None

# ===========================================================
# BACKGROUND SYNC
# ===========================================================
async def background_sync_task():
    global SYNC_STATUS
    if SYNC_STATUS["is_syncing"]:
        return

    SYNC_STATUS.update({
        "is_syncing": True,
        "progress": 0,
        "message": "Khởi tạo danh sách HOSE từ Listing API..."
    })
    print("=== Bat dau Sync Background (Historical-Only, 260 bars) ===")

    try:
        symbols_info = get_hose_symbols()
        if not symbols_info:
            SYNC_STATUS["message"] = "Lỗi: Không lấy được danh sách mã HOSE."
            return

        industry_map = {}
        for row in symbols_info:
            sym = row.get('symbol', '')
            # vnstock v3.5.0 Listing headers
            ind = row.get('icb_name3', row.get('icb_name2', row.get('industry_name', row.get('industry', row.get('organTypeCode', 'Khác')))))
            if sym:
                industry_map[sym] = ind if ind and str(ind).strip() and str(ind) != 'nan' else 'Khác'

        hose_symbols = list(industry_map.keys())
        print(f"Tong so ma HOSE: {len(hose_symbols)}")

        SYNC_STATUS["total"]        = len(hose_symbols)
        SYNC_STATUS["total_batches"] = max(1, (len(hose_symbols) + 99) // 100)
        SYNC_STATUS["message"]      = f"Tìm thấy {len(hose_symbols)} mã HOSE. Bắt đầu tải lịch sử..."

        results   = []
        batch_size = 100

        for batch_idx, i in enumerate(range(0, len(hose_symbols), batch_size)):
            chunk = hose_symbols[i:i + batch_size]
            SYNC_STATUS["current_batch"] = batch_idx + 1
            SYNC_STATUS["message"] = (
                f"Batch {batch_idx + 1}/{SYNC_STATUS['total_batches']} "
                f"({SYNC_STATUS['progress']}/{SYNC_STATUS['total']})"
            )

            for sym in chunk:
                stats = safe_fetch_trading_stats(sym)
                tech  = safe_fetch_quote_history(sym)

                if tech:
                    results.append({
                        "symbol":   sym,
                        "industry": industry_map.get(sym, 'Khác'),
                        **stats,
                        **tech
                    })

                SYNC_STATUS["progress"] += 1
                await asyncio.sleep(0.05)

            if i + batch_size < len(hose_symbols):
                SYNC_STATUS["message"] = f"Nghỉ 5s... ({SYNC_STATUS['progress']}/{SYNC_STATUS['total']})"
                print(f"[Batch {batch_idx + 1}] Nghi 5s.")
                await asyncio.sleep(5)

        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        SYNC_STATUS["message"] = f"Hoàn tất! {len(results)}/{len(hose_symbols)} mã."
        print(f"=== Sync xong: {len(results)} ma ===")

    except Exception as e:
        SYNC_STATUS["message"] = f"Lỗi: {str(e)}"
        print("Loi Sync:", repr(e))
    finally:
        SYNC_STATUS["is_syncing"] = False

# ===========================================================
# ROUTES
# ===========================================================
@app.get("/")
def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/status")
def get_status():
    return JSONResponse(SYNC_STATUS)

@app.post("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks):
    if not SYNC_STATUS["is_syncing"]:
        background_tasks.add_task(background_sync_task)
        return {"status": "started"}
    return {"status": "already_running"}

@app.get("/api/market-overview")
def get_market_overview():
    """Market overview 100% từ cache — ~0ms."""
    try:
        cached_data = load_cached_data()
        if not cached_data:
            return {
                "gainers": 0, "losers": 0, "unchanged": 0,
                "top_gainers": [], "top_losers": [], "total_stocks": 0,
                "error": "Chưa có dữ liệu. Vui lòng Sync."
            }

        df = pd.DataFrame(cached_data)
        for col in ['price_change', 'percent_change', 'close', 'volume']:
            df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)

        df['total_value'] = df['volume'] * df['close'] * 1000

        gainers   = int((df['price_change'] > 0).sum())
        losers    = int((df['price_change'] < 0).sum())
        unchanged = int((df['price_change'] == 0).sum())

        top_gainers = (
            df.nlargest(5, 'percent_change')[['symbol', 'percent_change', 'close', 'total_value', 'volume']]
            .to_dict('records')
        )
        top_losers = (
            df.nsmallest(5, 'percent_change')[['symbol', 'percent_change', 'close', 'total_value', 'volume']]
            .to_dict('records')
        )

        # Industry performance: average percent_change by industry
        industry_performance = {}
        if 'industry' in df.columns:
            # Group by industry and calculate mean percent change, count gainers/losers
            ind_stats = df.groupby('industry').agg({
                'percent_change': 'mean',
                'symbol': 'count',
                'volume': 'sum'
            })
            
            # Additional logic: calculate gainers/losers per industry
            for ind_name, group in df.groupby('industry'):
                if not ind_name or str(ind_name) == 'nan' or str(ind_name).strip() == '':
                    continue
                
                g = int((group['percent_change'] > 0).sum())
                l = int((group['percent_change'] < 0).sum())
                u = int((group['percent_change'] == 0).sum())
                avg_pct = round(float(group['percent_change'].mean()), 3)
                
                industry_performance[str(ind_name)] = {
                    "avg_pct": avg_pct,
                    "gainers": g,
                    "losers": l,
                    "unchanged": u,
                    "total": len(group),
                    "volume": float(group['volume'].sum())
                }

        return {
            "gainers":              gainers,
            "losers":               losers,
            "unchanged":            unchanged,
            "top_gainers":          top_gainers,
            "top_losers":           top_losers,
            "total_stocks":         len(df),
            "industry_performance": industry_performance,
        }

    except Exception as e:
        print("Loi market overview:", repr(e))
        return {"error": str(e)}

@app.get("/api/heatmap")
def get_heatmap(
    period: str = Query("1d", regex="^(1d|1w|1m|1q|1y)$"),
    metric: str = Query("price", regex="^(price|volume|net_volume)$"),
    top:    int = Query(200)
):
    """
    Trả về data heatmap nhóm theo ngành.
    - period: 1d | 1w | 1m | 1q | 1y
    - metric: price | volume | net_volume
    - top: số mã lấy theo volume cao nhất (mặc định 200)
    """
    METRIC_MAP = {
        "price":      {"1d": "pct_1d",     "1w": "pct_1w",     "1m": "pct_1m",     "1q": "pct_1q",     "1y": "pct_1y"},
        "volume":     {"1d": "vol_pct_1d", "1w": "vol_pct_1w", "1m": "vol_pct_1m", "1q": "vol_pct_1q", "1y": "vol_pct_1y"},
        "net_volume": {"1d": "net_vol_1d", "1w": "net_vol_1w", "1m": "net_vol_1m", "1q": "net_vol_1q", "1y": "net_vol_1y"},
    }

    try:
        cached_data = load_cached_data()
        if not cached_data:
            return {"data": [], "error": "Chưa có dữ liệu. Vui lòng Sync."}

        df = pd.DataFrame(cached_data)

        value_col = METRIC_MAP[metric][period]

        # Đảm bảo các cột tồn tại
        if value_col not in df.columns:
            return {"data": [], "error": f"Thiếu cột {value_col}. Vui lòng Sync lại để cập nhật dữ liệu."}

        df['volume']    = pd.to_numeric(df.get('volume', 0), errors='coerce').fillna(0)
        df['close']     = pd.to_numeric(df.get('close', 0), errors='coerce').fillna(0)
        df[value_col]   = pd.to_numeric(df[value_col], errors='coerce').fillna(0)

        # Lấy top N mã theo volume để heatmap không quá tải
        df = df.nlargest(top, 'volume')

        # Build output theo ngành
        result = []
        for _, row in df.iterrows():
            val = float(row.get(value_col, 0))
            result.append({
                "symbol":   str(row.get('symbol', '')),
                "industry": str(row.get('industry', 'Khác')),
                "value":    round(val, 3),
                "volume":   float(row.get('volume', 0)),
                "close":    float(row.get('close', 0)),
                "pct_1d":   round(float(row.get('pct_1d', 0)), 2),
            })

        # Sắp xếp theo ngành rồi volume để treemap layout đẹp hơn
        result.sort(key=lambda x: (x['industry'], -x['volume']))

        last_updated = os.path.getmtime(DATA_FILE) if os.path.exists(DATA_FILE) else 0

        return {
            "data":         result,
            "period":       period,
            "metric":       metric,
            "value_col":    value_col,
            "total":        len(result),
            "last_updated": last_updated
        }

    except Exception as e:
        print("Loi heatmap:", repr(e))
        return {"data": [], "error": str(e)}

@app.get("/api/potential-stocks")
def get_potential_stocks():
    """Bộ lọc cổ phiếu tiềm năng theo TA + FA."""
    data = load_cached_data()
    potentials = []

    for row in data:
        rsi     = row.get("rsi", 100)
        uptrend = row.get("is_uptrend", False)
        pe      = row.get("pe", 0)
        pb      = row.get("pb", 0)
        vol     = row.get("avg_match_volume_2w", 0)
        stoch_k = row.get("stoch_k", 100)

        is_oversold        = rsi <= 35 and stoch_k <= 20
        is_good_fundamental = 0 < pe < 20 and 0 < pb < 3
        has_volume         = vol > 100000

        if (is_oversold or uptrend) and is_good_fundamental and has_volume:
            potentials.append(row)

    potentials.sort(key=lambda x: (-1 if x.get("is_uptrend") else 0, x.get("rsi", 100)))

    last_updated = os.path.getmtime(DATA_FILE) if os.path.exists(DATA_FILE) else 0
    return {"data": potentials, "last_updated": last_updated}
