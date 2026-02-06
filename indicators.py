import requests
import pandas as pd
import numpy as np
import math
from datetime import datetime, timedelta


# ==========================================
# 1. 공통 유틸리티 함수 (데이터 조회 & 정밀도 보정)
# ==========================================

def fetch_binance_futures_data(symbol, interval='3m', limit=200):
    """바이낸스 USDT 선물 캔들 데이터 조회"""
    symbol = symbol.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'

    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])

        cols = ['open', 'high', 'low', 'close']
        df[cols] = df[cols].astype(float)

        # 한국 시간(KST) 변환
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms') + timedelta(hours=9)
        return df, symbol

    except Exception as e:
        print(f"❌ 데이터 조회 실패: {e}")
        return None, symbol


def fetch_symbol_tick_size(symbol):
    """
    [NEW] 거래소에서 해당 종목의 '가격 최소 단위(Tick Size)' 조회
    예: BTCUSDT -> 0.1, DOGEUSDT -> 0.00001
    """
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        response = requests.get(url)
        data = response.json()

        for s in data['symbols']:
            if s['symbol'] == symbol:
                for f in s['filters']:
                    if f['filterType'] == 'PRICE_FILTER':
                        return float(f['tickSize'])
    except Exception as e:
        print(f"⚠️ 틱 사이즈 조회 실패: {e}")

    return None # 실패 시 None 반환


def adjust_price(price, tick_size):
    """
    [NEW] 계산된 가격을 거래소 Tick Size에 맞춰 반올림
    자동매매 주문 시 필수적인 과정
    """
    if tick_size is None:
        return price

    # 예: price=100.123, tick=0.1 -> 100.1
    # 예: price=100.123, tick=0.05 -> 100.10
    adjusted = round(price / tick_size) * tick_size
    return adjusted


def get_decimal_places(tick_size):
    """Tick Size를 보고 출력할 소수점 자릿수(int) 계산"""
    if tick_size is None: return 2
    # 0.001 -> '001' -> 3자리
    s = f"{tick_size:.10f}".rstrip('0')
    if '.' in s:
        return len(s.split('.')[1])
    return 0


# ==========================================
# 2. 계산 로직 (ATR 밴드) - 변경 없음
# ==========================================

def calculate_atr_bands(df, length=3, multiplier=1):
    high, low, close = df['high'].values, df['low'].values, df['close'].values
    n = len(df)

    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

    atr = np.zeros(n)
    atr[length - 1] = np.mean(tr[:length])
    for i in range(length, n):
        atr[i] = (atr[i - 1] * (length - 1) + tr[i]) / length

    upper = close + (atr * multiplier)
    lower = close - (atr * multiplier)

    return upper, lower, atr


# ==========================================
# 3. 메인 실행 함수
# ==========================================

def main():
    print("\n🐳 고래지표 통합 계산기 (바이낸스 선물 3분봉)")
    print("사용법: /atr [종목]")
    print("예시: /atr btc")
    print("==================================================")

    while True:
        try:
            raw_input = input("\n명령어 입력 [종료: q]: ").strip()
            if raw_input.lower() in ['q', 'quit', 'exit']:
                print("종료합니다.")
                break

            parts = raw_input.split()
            if len(parts) < 2:
                print("⚠️  형식이 올바르지 않습니다. (예: /atr btc)")
                continue

            cmd = parts[0].lower()
            ticker = parts[1]

            if cmd not in ['/atr']:
                print("⚠️  알 수 없는 명령어입니다.")
                continue

            print(f"\n🔍 {ticker.upper()} 데이터 및 규칙 조회 중...")

            # 1. 캔들 데이터 조회
            df, full_symbol = fetch_binance_futures_data(ticker, interval='3m')

            # 2. 거래소 규칙(Tick Size) 조회 [추가됨]
            tick_size = fetch_symbol_tick_size(full_symbol)

            if df is None: continue

            # 공통 변수 설정
            idx = -2
            curr_time = df['datetime'].iloc[idx]
            curr_close = df['close'].iloc[idx]

            # 출력용 자릿수 계산 (f-string용)
            decimals = get_decimal_places(tick_size)

            print("-" * 50)
            print(f"📊 종목: {full_symbol}")
            print(f"📏 규칙(Tick): {tick_size} (출력: 소수점 {decimals}자리)")
            print(f"⏱️  기준: {curr_time} (KST, 직전 확정봉)")
            print(f"💰 종가: {curr_close:,.{decimals}f}")
            print("-" * 50)

            # 분기 처리
            if cmd == '/atr':
                # ATR 계산
                up, down, atr_val = calculate_atr_bands(df, length=3, multiplier=1)

                # [중요] 계산된 값을 거래소 규칙에 맞춰서 조정 (Rounding)
                final_up = adjust_price(up[idx], tick_size)
                final_down = adjust_price(down[idx], tick_size)
                # ATR 수치는 가격이 아니라 변동폭이므로 그냥 보여줘도 되지만, 깔끔하게 보기 위해 조정
                final_atr = adjust_price(atr_val[idx], tick_size)

                print(f"🎯 [ATR 밴드] (Len:3, Mult:1)")
                print(f"🔴 손절 상단: {final_up:,.{decimals}f}")
                print(f"🟢 손절 하단: {final_down:,.{decimals}f}")
                print(f"ℹ️  ATR 수치: {final_atr:,.{decimals}f}")

            print("==================================================")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")


if __name__ == "__main__":
    main()
