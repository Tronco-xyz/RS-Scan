import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="RS Rating Screener", layout="wide")
st.title("📊 RS Rating Screener (Relative Strength vs S&P 500)")

# --- Configuración ---
BENCHMARK = "SPY"
PERIOD = "1y"
INTERVAL = "1d"
nasdaq_100 = ["AAPL", "AMZN", "META", "MSFT", "NVDA"]  # Temporal: subset confiable

# --- Inputs del usuario ---
user_input = st.text_input("Agrega tickers adicionales separados por coma (opcional):")
extra_tickers = [t.strip().upper() for t in user_input.split(",") if t.strip()] if user_input else []

# --- Tickers a analizar ---
all_tickers = list(set(nasdaq_100 + extra_tickers))
st.write("📥 Ejecutando screener para:", all_tickers)

# --- Descargar benchmark ---
st.write("📈 Descargando datos y calculando RS Rating... Esto puede tardar unos segundos ⏳")
try:
    benchmark_download = yf.download(BENCHMARK, period=PERIOD, interval=INTERVAL)
    if "Close" in benchmark_download.columns:
        benchmark_data = benchmark_download[["Close"]]
    else:
        st.error("No se encontró 'Close' en el benchmark descargado.")
        st.stop()
    st.write("Datos del benchmark:", benchmark_data.shape)
except Exception as e:
    st.error(f"Error al descargar datos: {e}")
    st.stop()

# --- Descargar tickers ---
try:
    data_download = yf.download(all_tickers, period=PERIOD, interval=INTERVAL)
    if isinstance(data_download.columns, pd.MultiIndex):
        data = data_download["Close"]
    elif "Close" in data_download.columns:
        data = data_download[["Close"]]
        data.columns = [all_tickers[0]]
    elif isinstance(data_download, pd.Series):
        data = data_download.to_frame(name=all_tickers[0])
    else:
        st.error("Los datos descargados no tienen formato esperado ('Close').")
        st.stop()
    st.write("Datos de los tickers:", data.shape)
except Exception as e:
    st.error(f"Error al descargar datos: {e}")
    st.stop()

st.write("Tickers descargados:", list(data.columns))

# --- Función de cálculo del RS Score ---
def calc_rs_score(stock: pd.Series, benchmark: pd.Series):
    perf_stock = (
        0.4 * (stock / stock.shift(63)) +
        0.2 * (stock / stock.shift(126)) +
        0.2 * (stock / stock.shift(189)) +
        0.2 * (stock / stock.shift(252))
    )
    perf_bench = (
        0.4 * (benchmark / benchmark.shift(63)) +
        0.2 * (benchmark / benchmark.shift(126)) +
        0.2 * (benchmark / benchmark.shift(189)) +
        0.2 * (benchmark / benchmark.shift(252))
    )
    rs_score = (perf_stock / perf_bench) * 100
    rs_score = rs_score.iloc[252:]  # ignorar los primeros valores incompletos
    rs_score = rs_score.dropna()
    st.write("📈 RS Score generado:", rs_score.tail())
    return rs_score

# --- Procesar cada ticker ---
valid_scores = {}
new_high_flags = {}
failed_tickers = []

benchmark = benchmark_data.squeeze()
benchmark.index = benchmark.index.tz_localize(None)

for ticker in data.columns:
    try:
        stock = data[ticker].copy()
        stock.index = stock.index.tz_localize(None)
        st.write(f"⏳ Verificando {ticker}...", stock.tail())

        valid_count = stock.count()
        st.write(f"📊 {ticker} tiene {valid_count} valores válidos de precio.")

        combined = pd.concat([stock, benchmark], axis=1, join="inner")
        st.write(f"📆 {ticker} - Datos combinados (sin dropna):", combined.tail())
        combined = combined.dropna()
        st.write(f"✅ {ticker} - Después de dropna: {combined.shape[0]} filas")

        if combined.shape[0] < 100:
            st.warning(f"{ticker} tiene menos de 100 días válidos para RS.")
            failed_tickers.append(ticker)
            continue

        stock_aligned = combined.iloc[:, 0]
        bench_aligned = combined.iloc[:, 1]
        rs = calc_rs_score(stock_aligned, bench_aligned)

        if rs.dropna().shape[0] < 30:
            st.warning(f"{ticker} tiene muy pocos datos válidos después del cálculo.")
            failed_tickers.append(ticker)
            continue

        score = rs.iloc[-1]
        if pd.isna(score):
            st.warning(f"{ticker} tiene RS final NaN.")
            failed_tickers.append(ticker)
            continue

        last_value = rs.iloc[-1]
        max_value = rs[-252:].max(skipna=True)
        is_new_high = bool(last_value >= max_value)

        valid_scores[ticker] = score
        new_high_flags[ticker] = is_new_high

    except Exception as e:
        st.warning(f"No se pudo calcular RS para {ticker}: {e}")
        failed_tickers.append(ticker)

# --- Construir DataFrame de resultados ---
if valid_scores:
    df_result = pd.DataFrame({
        "Ticker": list(valid_scores.keys()),
        "RS Score": list(valid_scores.values()),
        "RS New High": [new_high_flags[t] for t in valid_scores.keys()]
    })
    df_result["RS Rating"] = df_result["RS Score"].rank(pct=True) * 100
    df_result["RS Rating"] = df_result["RS Rating"].round(0).astype(int)
    df_result = df_result.sort_values(by="RS Rating", ascending=False)

    st.success("✅ Screener completo.")
    st.dataframe(df_result)

    # Botón para exportar CSV
    csv = df_result.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Descargar CSV", csv, "rs_rating_screener.csv", "text/csv")

else:
    st.warning("No se pudo calcular el RS Rating para ningún ticker. Revisa los datos descargados.")
    st.write("❌ Tickers fallidos:", failed_tickers)
