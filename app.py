import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# ✅ ESTA LÍNEA DEBE SER LA PRIMERA DE STREAMLIT
st.set_page_config(page_title="RS Rating Screener", layout="wide")

st.title("📊 RS Rating Screener (Relative Strength vs S&P 500)")

# --- Configuraciones iniciales ---
BENCHMARK = "SPY"
PERIOD = "1y"
INTERVAL = "1d"

# Subconjunto más pequeño de tickers para pruebas
nasdaq_100 = ["AAPL", "MSFT", "AMZN", "NVDA", "META"]

# --- UI ---
user_tickers = st.text_input("Agrega tickers adicionales separados por coma (opcional):")
custom_tickers = [x.strip().upper() for x in user_tickers.split(",") if x.strip() != ""]
all_tickers = list(set(nasdaq_100 + custom_tickers))  # SPY se descarga aparte

if st.button("🔍 Ejecutar Screener"):
    st.info("Descargando datos y calculando RS Rating... Esto puede tardar unos segundos ⏳")

    try:
        # Descargar datos del benchmark SPY por separado
        benchmark_download = yf.download(BENCHMARK, period=PERIOD, interval=INTERVAL)
        if benchmark_download.empty:
            st.error(f"No se pudieron obtener datos del benchmark ({BENCHMARK})")
            st.stop()

        if "Close" in benchmark_download.columns:
            benchmark_data = benchmark_download["Close"]
        else:
            st.error("No se encontró 'Close' en el benchmark descargado.")
            st.stop()

        # Descargar datos del resto de tickers
        data_download = yf.download(all_tickers, period=PERIOD, interval=INTERVAL)
        if data_download.empty:
            st.error("No se pudieron descargar datos del resto de los tickers.")
            st.stop()

        # ✅ Manejo robusto dependiendo del número de tickers
        if isinstance(data_download.columns, pd.MultiIndex):
            if "Close" in data_download.columns.levels[0]:
                data = data_download["Close"]
            else:
                st.error("No se encontró 'Close' en los datos descargados.")
                st.write("Columnas recibidas:", data_download.columns.levels[0].tolist())
                st.stop()
        elif isinstance(data_download, pd.DataFrame):
            data = data_download[["Close"]]
            data.columns = [all_tickers[0]]
        elif isinstance(data_download, pd.Series):
            data = data_download.to_frame(name=all_tickers[0])
        else:
            st.error("Formato de datos inesperado al descargar tickers.")
            st.stop()

    except Exception as e:
        st.error(f"Error al descargar datos: {e}")
        st.stop()

    st.write("Datos del benchmark:", benchmark_data.shape)
    st.write("Datos de los tickers:", data.shape)
    st.write("Tickers descargados:", list(data.columns))

    benchmark = benchmark_data.squeeze()
    benchmark.index = benchmark.index.tz_localize(None)

    def calc_rs_score(stock, benchmark):
        perf_63 = stock / stock.shift(63)
        perf_126 = stock / stock.shift(126)
        perf_189 = stock / stock.shift(189)
        perf_252 = stock / stock.shift(252)

        bench_63 = benchmark / benchmark.shift(63)
        bench_126 = benchmark / benchmark.shift(126)
        bench_189 = benchmark / benchmark.shift(189)
        bench_252 = benchmark / benchmark.shift(252)

        rs_stock = 0.4 * perf_63 + 0.2 * perf_126 + 0.2 * perf_189 + 0.2 * perf_252
        rs_bench = 0.4 * bench_63 + 0.2 * bench_126 + 0.2 * bench_189 + 0.2 * bench_252

        rs_score = (rs_stock / rs_bench) * 100
        return rs_score

    rs_scores = {}
    new_high_flags = {}
    failed_tickers = []

    for ticker in data.columns:
        try:
            valid_count = data[ticker].count()
            st.write(f"📊 {ticker} tiene {valid_count} valores válidos de precio.")
            stock = data[ticker].copy()
            stock.index = stock.index.tz_localize(None)
            st.write(f"⏳ Verificando {ticker}...", stock.tail())
            rs = calc_rs_score(stock, benchmark)
            st.write(f"📈 RS calculado para {ticker}:", rs.tail())

            if rs.dropna().shape[0] < 100:
                st.warning(f"{ticker} tiene menos de 100 días válidos para RS.")
                failed_tickers.append(ticker)
                continue

            score = rs.iloc[-1]
            if pd.isna(score):
                st.warning(f"{ticker} tiene RS final NaN.")
                failed_tickers.append(ticker)
                continue

            rs_scores[ticker] = score
            last_value = rs.iloc[-1]
            max_value = rs[-252:].max(skipna=True)
            is_new_high = bool(last_value >= max_value)
            new_high_flags[ticker] = is_new_high
        except Exception as e:
            failed_tickers.append(ticker)
            st.warning(f"No se pudo calcular RS para {ticker}: {e}")

    st.write("✅ Tickers con datos válidos:", list(rs_scores.keys()))
    st.write("❌ Tickers fallidos:", failed_tickers)

    df_rs = pd.DataFrame.from_dict(rs_scores, orient="index", columns=["RS_Score"])
    df_rs.dropna(inplace=True)

    if df_rs.empty:
        st.warning("No se pudo calcular el RS Rating para ningún ticker. Revisa los datos descargados.")
        st.stop()

    df_rs["RS_Rating"] = df_rs["RS_Score"].rank(pct=True) * 100
    df_rs["RS_Rating"] = df_rs["RS_Rating"].round(0).astype(int)
    df_rs["RS_New_High"] = df_rs.index.map(new_high_flags)

    st.subheader("🎯 Filtro: RS Rating > 80")
    filtered_df = df_rs[df_rs["RS_Rating"] > 80].sort_values(by="RS_Rating", ascending=False)
    st.dataframe(filtered_df, use_container_width=True)

    with st.expander("📋 Ver todos los resultados"):
        st.dataframe(df_rs.sort_values(by="RS_Rating", ascending=False), use_container_width=True)

    csv = df_rs.to_csv().encode("utf-8")
    st.download_button("📥 Descargar CSV completo", data=csv, file_name="rs_rating_screener.csv", mime="text/csv")
