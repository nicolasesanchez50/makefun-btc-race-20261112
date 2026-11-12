# cbBTC dip-reversal race bot

A long-only mean-reversion bot for make.fun's `agent-fun/bars-replay/v1`
competition. It trades Coinbase Wrapped BTC (cbBTC) against USDC on one-minute
on-chain pool bars from the Orca Whirlpool.

## Strategy

The bot stays in cash unless price has flushed:

- Measure the change over the last 45 one-minute closes.
- If price is 50 bps or more below where it was 45 bars ago, buy with the
  available cash at the next bar's open.
- Sell when the position is 125 bps above the entry close, 200 bps below it,
  or after 120 bars, whichever comes first.
- Stay flat for 90 bars after an exit.

A full round trip costs about 26 bps after the fee, the modelled slippage and
the order's price impact, so only a move clearly larger than that is worth
trading. On its first two batches the bot sends a two-USDC probe round trip, so
the window always holds at least one own filled order even when no dip
qualifies.

## Files

- `main.py` — the bot (Python 3.13, standard library only).
- `vendor/makefun_bars.py` — the kit's protocol shim, copied byte for byte.
- `LICENSE` — MIT.
