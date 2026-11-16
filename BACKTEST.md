# Simulación de estrategias (60 sesiones: 2026-08-21 a 2026-11-13)

Presupuesto 1150 $, máx. 2 posiciones, comisiones IBKR Fixed, deslizamiento 0.02 % por lado. 49 valores.

Referencia: comprar SPY y no tocarlo en el mismo periodo = -1.54 %

| Estrategia | Periodo | dias | operaciones | resultado_$ | resultado_% | aciertos_% | ganancia_media_$ | perdida_media_$ | factor_beneficio | comisiones_$ | peor_caida_$ | dias_positivos_% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_actual | Todo | 60 | 48 | -102.5 | -8.91 | 22.9 | 4.74 | -4.18 | 0.34 | 96.0 | -102.5 | 3.3 |
| A_actual | Primeros 2/3 (elección) | 40 | 48 | -102.5 | -8.91 | 22.9 | 4.74 | -4.18 | 0.34 | 96.0 | -102.5 | 5.0 |
| A_actual | Último 1/3 (comprobación) | 20 | 0 | 0.0 | 0.0 | 0 | 0 | 0 | None | 0 | 0.0 | 0.0 |
| B_filtro | Todo | 60 | 29 | -89.5 | -7.78 | 10.3 | 4.31 | -3.94 | 0.13 | 58.0 | -89.5 | 1.7 |
| B_filtro | Primeros 2/3 (elección) | 40 | 28 | -83.4 | -7.25 | 10.7 | 4.31 | -3.85 | 0.13 | 56.0 | -83.4 | 2.5 |
| B_filtro | Último 1/3 (comprobación) | 20 | 1 | -6.11 | -0.53 | 0.0 | 0 | -6.11 | 0.0 | 2.0 | -6.11 | 0.0 |
| C_atr | Todo | 60 | 59 | -195.38 | -16.99 | 23.7 | 8.2 | -6.89 | 0.37 | 118.0 | -195.38 | 15.0 |
| C_atr | Primeros 2/3 (elección) | 40 | 30 | -67.69 | -5.89 | 33.3 | 7.27 | -7.02 | 0.52 | 60.0 | -86.86 | 15.0 |
| C_atr | Último 1/3 (comprobación) | 20 | 29 | -127.69 | -11.1 | 13.8 | 10.55 | -6.8 | 0.25 | 58.0 | -127.69 | 15.0 |
| D_orb | Todo | 60 | 86 | -147.9 | -12.86 | 34.9 | 4.18 | -4.88 | 0.46 | 172.0 | -156.02 | 20.0 |
| D_orb | Primeros 2/3 (elección) | 40 | 58 | -91.75 | -7.98 | 36.2 | 4.3 | -4.92 | 0.5 | 116.0 | -109.25 | 27.5 |
| D_orb | Último 1/3 (comprobación) | 20 | 28 | -56.15 | -4.88 | 32.1 | 3.9 | -4.8 | 0.38 | 56.0 | -56.44 | 5.0 |
| E_orb_sin_filtro | Todo | 60 | 107 | -300.27 | -26.11 | 29.9 | 4.8 | -6.05 | 0.34 | 214.0 | -300.27 | 18.3 |
| E_orb_sin_filtro | Primeros 2/3 (elección) | 40 | 94 | -255.14 | -22.19 | 30.9 | 4.93 | -6.12 | 0.36 | 188.0 | -267.58 | 27.5 |
| E_orb_sin_filtro | Último 1/3 (comprobación) | 20 | 13 | -45.14 | -3.92 | 23.1 | 3.59 | -5.59 | 0.19 | 26.0 | -45.14 | 0.0 |

## Estrategias
- **A_actual**: Actual: cruce EMA 9/21 + VWAP + RSI 50-70, stop 0,75 %, objetivo 1,5 %
- **B_filtro**: A + solo compra si el mercado (SPY) está alcista
- **C_atr**: B + stop según volatilidad (1,5 x ATR), objetivo 2x el stop
- **D_orb**: Ruptura del rango de los primeros 30 min con volumen, filtro de mercado
- **E_orb_sin_filtro**: D sin filtro de mercado
