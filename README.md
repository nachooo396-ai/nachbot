# NachBot

Bot de trading intradía para Alpaca. **Por defecto opera con dinero ficticio** (cuenta de práctica).

## Qué hace
- Mientras la bolsa de EE. UU. está abierta (15:30–22:00 hora de España), cada 5 minutos revisa 10 acciones/ETF muy líquidos:
  SPY, QQQ, AAPL, MSFT, NVDA, AMD, META, AMZN, TSLA, GOOGL.
- **Compra** cuando hay impulso al alza: la media de 9 velas cruza por encima de la de 21, el precio está sobre el VWAP del día y el RSI está entre 50 y 70.
- Cada compra lleva **objetivo de ganancia +1,5 %** y **stop de pérdida −0,75 %** puestos desde el primer momento.
- Nunca deja nada abierto de un día para otro: cierra todo 10 min antes del cierre.

## Capital controlado y retirada de ganancias
- Opera solo con `BUDGET` (1.150 $ ≈ 1.000 €), aunque la cuenta tenga más.
- Lo que gane **se aparta y no se reinvierte**: en cada ejecución verás "Ganancias apartadas para retirar".
- Si pierde, opera con lo que queda: nunca mete dinero extra.
- La retirada en sí se hace a mano desde el bróker (los brókers no dejan sacar dinero desde un bot).

## Frenos de seguridad
| Freno | Por defecto |
|---|---|
| Máx. posiciones a la vez | 3 |
| Riesgo máx. por operación | 1 % del capital |
| Máx. operaciones al día | 8 |
| Stop del día (cierra todo y para) | −3 % del presupuesto en el día |
| Apagado total | −25 % del presupuesto acumulado |
| Sin entradas | primeros 15 min y últimos 30 min |

Todo se ajusta en `.github/workflows/bot.yml` (variables `BUDGET`, etc.).

## Ver qué ha hecho
GitHub → pestaña **Actions** → cualquier ejecución de "NachBot" → resumen con capital, ganancias y compras.
Las operaciones también se ven en el panel de Alpaca.

## Pruebas sin conexión
```
ALPACA_KEY=x ALPACA_SECRET=y python3 test_bot.py
```

## Pasar a dinero real (más adelante, no ahora)
Solo si tras 2–3 meses en práctica le gana a comprar el S&P 500 y no tocarlo. Habría que abrir cuenta real
en un bróker con API que acepte residentes en España, cambiar las claves, `LIVE: "true"`, `START_EQUITY` = saldo real
y empezar con poco.

## Ver el estado sin entrar en Actions
Rama **estado** del repositorio: `ESTADO.md` (última ejecución) y `REGISTRO.md` (historial).
