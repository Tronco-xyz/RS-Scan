...
            stock = data[ticker].copy()
            stock.index = stock.index.tz_localize(None)
            st.write(f"⏳ Verificando {ticker}...", stock.tail())

            combined = pd.concat([stock, benchmark], axis=1, join='inner')
            st.write(f"📆 {ticker} - Datos combinados (sin dropna):", combined.tail())
            combined = combined.dropna()
            st.write(f"✅ {ticker} - Después de dropna: {combined.shape[0]} filas")

            stock_aligned = combined.iloc[:, 0]
            bench_aligned = combined.iloc[:, 1]
            rs = calc_rs_score(stock_aligned, bench_aligned)
...
