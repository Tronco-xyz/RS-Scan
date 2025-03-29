import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="RS Rating Screener", layout="wide")

st.title("📊 RS Rating Screener (Relative Strength vs S&P 500)")

# --- Configuraciones iniciales ---
BENCHMARK = "SPY"  # Usamos SPY en lugar de ^GSPC por mayor estabilidad
PERIOD = "1y"
INTERVAL = "1d"

# Lista base: Nasdaq 100
nasdaq_100 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "PEP", "AVGO", "COST",
    "CSCO", "TMUS", "TXN", "ADBE", "QCOM", "AMGN", "INTU", "HON", "INTC", "SBUX",
    "VRTX", "ADI", "ISRG", "MDLZ", "GILD", "REGN", "FISV", "BKNG", "LRCX", "ADP",
    "PDD", "PANW", "CDNS", "MU", "ASML", "KDP", "CSGP", "MNST", "MELI", "CHTR",
    "AEP", "IDXX", "ORLY", "ROST", "PAYX", "CTAS", "MRNA", "CRWD", "MAR", "FTNT",
    "DLTR", "ODFL", "EXC", "WBA", "LCID", "BIIB", "AZN", "TEAM", "ZM", "SIRI"
]

# --- UI ---
user_tickers = st.text_input("Agrega tickers adicionales separados por coma (opcional):")
custom_tickers = [x.strip().upper() for x in user_tickers.split(",") if x.strip() != ""]
all_tickers = list(set(nasdaq_100 + custom_tickers + [BENCHMARK]))

if st.button("🔍 Ejecutar Screener"):
    st.info("Descargando datos y calculando RS Rating... Esto puede tardar unos segundos ⏳")

    try:
        # Descargar precios ajustados de cierre
        data = yf.download(all_tickers, period=PERIOD, interval=INTERVAL)["Adj Close"]

        if data.empty:
            st.error("No se pudieron descargar datos. La respuesta de Yahoo Finance está vacía.")
            st.stop()

        if BENCHMARK not in data.columns:
            st.error(f"El benchmark ({BENCHMARK}) no se encuentra en los datos descargados.")
            st.write("Tickers disponibles:", list(data.columns))
            st.stop()

        # Forzar a DataFrame si solo un ticker
        if isinstance(data, pd.Series):
            data = data.to_frame()

    except Exception as e:
        st.error(f"Error al descargar datos: {e}")
        st.stop()

    # Benchmark separado
    benchmark = data[BENCHMARK]

    # Función para calcular RS Score
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

    # Calcular RS Scores al día más reciente
    rs_scores = {}
    new_high_flags = {}
    for ticker in data.columns:
        if ticker == BENCHMARK:
            continue
        try:
            rs = calc_rs_score(data[ticker], benchmark)
            rs_scores[ticker] = rs.iloc[-1]
            new_high_flags[ticker] = rs.iloc[-1] >= rs.max()
        except Exception as e:
            st.warning(f"No se pudo calcular RS para {ticker}: {e}")

    # Convertir a DataFrame
    df_rs = pd.DataFrame.from_dict(rs_scores, orient="index", columns=["RS_Score"])
    df_rs.dropna(inplace=True)

    # Calcular ranking percentil (RS Rating)
    df_rs["RS_Rating"] = df_rs["RS_Score"].rank(pct=True) * 100
    df_rs["RS_Rating"] = df_rs["RS_Rating"].round(0).astype(int)

    # Agregar señal de nuevo máximo de RS Score
    df_rs["RS_New_High"] = df_rs.index.map(new_high_flags)

    # Filtro de RS Rating > 80
    st.subheader("🎯 Filtro: RS Rating > 80")
    filtered_df = df_rs[df_rs["RS_Rating"] > 80].sort_values(by="RS_Rating", ascending=False)
    st.dataframe(filtered_df, use_container_width=True)

    # Mostrar todo (opcional)
    with st.expander("📋 Ver todos los resultados"):
        st.dataframe(df_rs.sort_values(by="RS_Rating", ascending=False), use_container_width=True)

    # Exportar CSV
    csv = df_rs.to_csv().encode("utf-8")
    st.download_button("📥 Descargar CSV completo", data=csv, file_name="rs_rating_screener.csv", mime="text/csv")
