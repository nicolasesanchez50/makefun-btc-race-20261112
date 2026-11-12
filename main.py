#!/usr/bin/env python3
"""cbBTC dip-reversal bot for make.fun's agent-fun/bars-replay/v1 replay.

Thesis: on Solana's cbBTC/USDC Orca pool, price rarely trends in a straight
line for hours; it steps down in flushes and then bounces. A long-only bot
therefore stays in cash most of the time and buys after a short-window flush,
selling into the bounce. A round trip costs about 26 bps (4 bps fee per side,
2 bps slippage per side, plus the order's own price impact), so the target has
to be clearly larger than that cost: 125 bps of profit, with a 200 bps stop
and a two-hour time stop to keep a losing flush from turning into a hold.

The bot also sends a two-USDC probe round trip on its first two batches: the
race guardrail requires at least one own filled order, and a window with no
qualifying dip must still show that the bot traded. The probe is sized so its
cost is a rounding error, and it never blocks a real signal for long.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
BPS = 10_000

# Signal, in one-minute bars.
LOOK = 45            # bars used to measure the flush
ENTRY_BPS = 50       # buy after a LOOK-bar drop of at least this many bps
TP_BPS = 125         # take profit this far above the entry close
STOP_BPS = 200       # hard stop this far below the entry close
MAX_HOLD = 120       # time stop, in bars
COOLDOWN = 90        # bars to stay flat after an exit
MAX_SLIPPAGE_BPS = 250

# The probe: a tiny round trip on the first two batches, so the window always
# has at least one own filled order even when no dip qualifies.
PROBE_NOTIONAL = 2_000_000   # 2 USDC in quote units
MIN_NOTIONAL = 1_000_000     # 1 USDC, the market's minimum buy


class Bot:
    def __init__(self):
        self.closes = []
        self.entry_px = None
        self.entry_bar = None
        self.cooldown = 0
        self.probed = False
        self.probe_held = False

    def dip_bps(self):
        """The LOOK-bar change in bps, or 0 before there is enough history."""
        if len(self.closes) <= LOOK:
            return 0.0
        return (self.closes[-1] / self.closes[-1 - LOOK] - 1.0) * BPS

    def on_batch(self, state, batch):
        close = state.close(SYMBOL)
        if close is None:
            return []
        self.closes.append(close)
        held = state.positions.get(SYMBOL)

        # Probe round trip first: one buy, one sell, about three cents of cost.
        if self.probe_held:
            if held is not None:
                self.probe_held = False
                return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            self.probe_held = False
        if not self.probed and held is None and state.cash >= MIN_NOTIONAL:
            self.probed = True
            notional = min(state.cash, PROBE_NOTIONAL)
            if notional >= MIN_NOTIONAL:
                self.probe_held = True
                return [{"side": "buy", "symbol": SYMBOL,
                         "notional_quote_units": notional,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]

        if self.cooldown > 0:
            self.cooldown -= 1

        if held is None:
            self.entry_px = None
            self.entry_bar = None
            if self.cooldown > 0 or len(self.closes) <= LOOK:
                return []
            if self.dip_bps() <= -ENTRY_BPS:
                notional = min(state.cash, state.weight_room(SYMBOL))
                if notional >= MIN_NOTIONAL:
                    self.entry_px = close
                    self.entry_bar = len(self.closes) - 1
                    return [{"side": "buy", "symbol": SYMBOL,
                             "notional_quote_units": notional,
                             "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            return []

        if self.entry_px is None:
            self.entry_px = close
            self.entry_bar = len(self.closes) - 1
        gain_bps = (close / self.entry_px - 1.0) * BPS
        held_bars = len(self.closes) - 1 - self.entry_bar
        if gain_bps >= TP_BPS or gain_bps <= -STOP_BPS or held_bars >= MAX_HOLD:
            self.cooldown = COOLDOWN
            self.entry_px = None
            self.entry_bar = None
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []


def main():
    bot = Bot()
    makefun_bars.run(bot.on_batch)


if __name__ == "__main__":
    main()
