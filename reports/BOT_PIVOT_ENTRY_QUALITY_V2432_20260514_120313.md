# V24.3.2 - ENTRY QUALITY REPORT

- log: `logs/BOT_PIVOT_07D_24_7_DEMO_20260514_110629.log`
- lines in source: `11099`
- lines scanned: `11099` from line `1`

## Summary by asset

| Asset | NEW | LIMIT_OK | FILL | TP_OK | CANCEL | cancel age avg/max | REJ far | REJ market | WIDTH small | BB width OK | L1/price avg/max | dist_ratio avg/max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | 0 | 0 | 0 | 0 | 0 | - | 28 | 0 | 0 | 100% | - | - |
| EURUSD | 2 | 6 | 1 | 1 | 0 | - | 0 | 8 | 0 | 100% | 0.0004/0.0005 | 0.420/0.510 |
| BTCUSD | 0 | 0 | 0 | 0 | 0 | - | 14 | 4 | 0 | 100% | - | - |
| ETHUSD | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 27 | 0% | - | - |
| UNKNOWN | 0 | 9 | 2 | 2 | 0 | - | 1 | 0 | 6 | - | - | - |
| DE40 | 1 | 3 | 0 | 0 | 1 | 344.7/344.7s | 10 | 0 | 0 | 100% | 28.5000/28.5000 | 0.633/0.633 |
| EURJPY | 1 | 3 | 0 | 0 | 1 | 339.8/339.8s | 0 | 0 | 12 | 20% | 0.0480/0.0480 | 0.267/0.267 |
| GBPUSD | 3 | 9 | 0 | 0 | 3 | 337.9/342.1s | 0 | 0 | 0 | 100% | 0.0009/0.0010 | 0.770/0.825 |
| FILTER | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 12 | 40% | - | - |
| USDJPY | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 9 | 0% | - | - |
| SILVER | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 6 | 0% | - | - |
| L1 | 0 | 0 | 0 | 0 | 0 | - | 1 | 0 | 0 | - | 4.9867/8.2500 | 0.227/0.375 |
| J225 | 0 | 0 | 0 | 0 | 0 | - | 2 | 0 | 0 | 100% | - | - |
| US500 | 0 | 0 | 0 | 0 | 0 | - | 2 | 0 | 0 | 100% | - | - |
| LIMITS | 3 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |

## Last observed entry/cancel context

- US100: width line 8422 width=59.31184 required=30.00000 ratio=1.977 ok=True
- EURUSD: entry line 10485 L1=1.16991 dist=0.0005100000 dist_ratio=0.510 width line 10483 width=0.00121 required=0.00040 ratio=3.014 ok=True
- BTCUSD: width line 8065 width=560.64657 required=150.00000 ratio=3.738 ok=True
- ETHUSD: width line 7878 width=13.23737 required=15.00000 ratio=0.882 ok=False
- DE40: entry line 548 L1=24409.1 dist=28.5000000000 dist_ratio=0.633 cancel line 1654 age=344.7s width line 7116 width=56.67361 required=30.00000 ratio=1.889 ok=True
- EURJPY: entry line 9380 L1=184.942 dist=0.0480000000 dist_ratio=0.267 cancel line 10502 age=339.8s width line 9378 width=0.11959 required=0.10000 ratio=1.196 ok=True
- GBPUSD: entry line 7857 L1=1.35189 dist=0.0008000000 dist_ratio=0.667 cancel line 8987 age=342.1s width line 7855 width=0.00082 required=0.00050 ratio=1.633 ok=True
- FILTER: width line 10681 width=10.33387 required=8.00000 ratio=1.292 ok=True
- USDJPY: width line 3271 width=0.06335 required=0.08000 ratio=0.792 ok=False
- SILVER: width line 9204 width=0.54018 required=1.00000 ratio=0.540 ok=False
- L1: entry line 10683 L1=4689.11 dist=3.7800000000 dist_ratio=0.172
- J225: width line 8982 width=191.86313 required=100.00000 ratio=1.919 ok=True
- US500: width line 4694 width=10.38728 required=10.00000 ratio=1.039 ok=True

## Reject reasons

- US100: BOLLINGER_TOO_FAR=28
- BTCUSD: BOLLINGER_TOO_FAR=14, MARKETABLE_LIMIT=4
- ETHUSD: BOLLINGER_WIDTH_TOO_SMALL=18
- DE40: BOLLINGER_TOO_FAR=10
- EURJPY: BOLLINGER_WIDTH_TOO_SMALL=8
- EURUSD: MARKETABLE_LIMIT=8
- UNKNOWN: BOLLINGER_WIDTH_TOO_SMALL=6, BOLLINGER_TOO_FAR=1
- FILTER: BOLLINGER_WIDTH_TOO_SMALL=6
- USDJPY: BOLLINGER_WIDTH_TOO_SMALL=6
- SILVER: BOLLINGER_WIDTH_TOO_SMALL=4
- J225: BOLLINGER_TOO_FAR=2
- US500: BOLLINGER_TOO_FAR=2
- L1: BOLLINGER_TOO_FAR=1
