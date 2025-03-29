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

        if "Adj Close" in benchmark_download.columns:
            benchmark_data = benchmark_download["Adj Close"]
        else:
            benchmark_data = benchmark_download.iloc[:, 0]  # Fallback a la primera columna

        # Descargar datos del resto de tickers
        data = yf.download(all_tickers, period=PERIOD, interval=INTERVAL)["Adj Close"]
        if data.empty:
            st.error("No se pudieron descargar datos del resto de los tickers.")
            st.stop()

        if isinstance(data, pd.Series):
            data = data.to_frame()

    except Exception as e:
        st.error(f"Error al descargar datos: {e}")
        st.stop()

    st.write("Datos del benchmark:", benchmark_data.shape)
    st.write("Datos de los tickers:", data.shape)
    st.write("Tickers descargados:", list(data.columns))

    benchmark = benchmark_data

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
            rs = calc_rs_score(data[ticker], benchmark)
            score = rs.iloc[-1]
            if pd.isna(score):
                failed_tickers.append(ticker)
                continue
            rs_scores[ticker] = score
            new_high_flags[ticker] = score >= rs.max()
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
