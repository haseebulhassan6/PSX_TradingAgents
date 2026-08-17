# PSX KMI30 Scanner Setup

This branch adds a deterministic KMI30 daily breakout scanner. Numeric levels are calculated in Python from PSX OHLCV data. OmniRoute is used only as a final risk reviewer and is not allowed to invent or change levels.

## Requirements

- Windows 10/11
- Python 3.11 or 3.12
- Git
- OmniRoute running locally on port 20128

## Install

```powershell
git clone https://github.com/haseebulhassan6/PSX_TradingAgents.git
cd PSX_TradingAgents
git checkout psx-kmi30-v1

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

## Configure OmniRoute

Create `.env` from the supplied template:

```powershell
Copy-Item .env.psx.example .env
notepad .env
```

Set your newly generated OmniRoute endpoint key locally:

```env
TRADINGAGENTS_LLM_PROVIDER=openai_compatible
TRADINGAGENTS_LLM_BACKEND_URL=http://localhost:20128/v1
OPENAI_COMPATIBLE_API_KEY=YOUR_NEW_OMNIROUTE_KEY
TRADINGAGENTS_DEEP_THINK_LLM=auto
TRADINGAGENTS_QUICK_THINK_LLM=auto
TRADINGAGENTS_TEMPERATURE=0.0
```

Do not commit `.env`. It is already ignored by Git.

## Check OmniRoute

```powershell
Test-NetConnection localhost -Port 20128
curl.exe http://localhost:20128/v1/models -H "Authorization: Bearer YOUR_NEW_OMNIROUTE_KEY"
```

The TCP test must show `TcpTestSucceeded : True`. The models request should return JSON instead of a connection error.

## Run the KMI30 scanner

Normal run with OmniRoute final review:

```powershell
psx-kmi30
```

Equivalent module form:

```powershell
python -m psx_scanner
```

Run the deterministic scanner without any AI call:

```powershell
psx-kmi30 --no-ai
```

Show diagnostics for all KMI30 stocks:

```powershell
psx-kmi30 --show-all --no-ai
```

Limit final confirmed setups to three:

```powershell
psx-kmi30 --limit 3
```

## Confirmation rules in v1

A BUY candidate must have all of the following:

- latest completed daily close above established recent resistance
- volume at least 1.2x its 20-day average; 1.5x receives the stronger score
- close above EMA20 and EMA50
- RSI between 50 and 80, with 55-75 preferred
- bullish daily candle with a strong body and limited upper rejection
- price no more than 10% above EMA20
- structure-based stop below the breakout/recent swing area
- calculated reward/risk of at least 2.0

If no stock passes every mandatory rule, the program prints:

`NO CONFIRMED KMI30 BREAKOUT TODAY — WAIT.`

## Data

KMI30 membership is read from the PSX Data Portal each run. Full daily OHLCV is obtained through `psxdata`, which uses public PSX data. The scanner deliberately refuses to create a BUY when full OHLCV is unavailable.

## Security

Never paste API keys into source code, GitHub issues, commits, screenshots, or chat. If a key has been exposed, revoke it and create a new one before using this setup.
