# Simulación de estrategias (250 sesiones: 2025-11-17 a 2026-11-13)

Presupuesto 1150 $, máx. 2 posiciones, deslizamiento 0.02 % por lado. 0 valores.

## Trading 212 con saldo en dólares (0 comisión, solo diferencial)

| Estrategia | Periodo | operaciones | resultado % | aciertos % | factor beneficio | comisiones $ | peor caída $ |
|---|---|---|---|---|---|---|---|
| A_actual | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| A_actual | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| A_actual | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| B_filtro | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| B_filtro | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| B_filtro | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| C_atr | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| C_atr | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| C_atr | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| D_orb | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| D_orb | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| D_orb | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| E_orb_sin_filtro | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| E_orb_sin_filtro | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| E_orb_sin_filtro | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| F_rebote | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| F_rebote | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| F_rebote | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| G_rebote_filtro | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| G_rebote_filtro | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| G_rebote_filtro | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |

## Interactive Brokers Fixed (0,005 $/acc, mín. 1 $)

| Estrategia | Periodo | operaciones | resultado % | aciertos % | factor beneficio | comisiones $ | peor caída $ |
|---|---|---|---|---|---|---|---|
| A_actual | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| A_actual | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| A_actual | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| B_filtro | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| B_filtro | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| B_filtro | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| C_atr | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| C_atr | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| C_atr | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| D_orb | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| D_orb | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| D_orb | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| E_orb_sin_filtro | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| E_orb_sin_filtro | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| E_orb_sin_filtro | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| F_rebote | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| F_rebote | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| F_rebote | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| G_rebote_filtro | Todo | 0 | 0.0 | 0 | None | 0 | 0.0 |
| G_rebote_filtro | 1ª parte (2/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |
| G_rebote_filtro | 2ª parte (1/3) | 0 | 0.0 | 0 | None | 0 | 0.0 |

## Estrategias
- **A_actual**: Actual: cruce EMA 9/21 + VWAP + RSI 50-70, stop 0,75 %, objetivo 1,5 %
- **B_filtro**: A + solo compra si el mercado (SPY) está alcista
- **C_atr**: B + stop según volatilidad (1,5 x ATR), objetivo 2x el stop
- **D_orb**: Ruptura del rango de los primeros 30 min con volumen, filtro de mercado
- **E_orb_sin_filtro**: D sin filtro de mercado
- **F_rebote**: Rebote: compra caídas bruscas bajo el VWAP (2 ATR, RSI<25), objetivo 1,5 ATR, stop 1,5 ATR
- **G_rebote_filtro**: F solo con el mercado (SPY) alcista
