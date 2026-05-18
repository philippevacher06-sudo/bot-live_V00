import os, json, glob, time, functools, datetime

G = {}
BUSY = False
STATE = os.getenv("V2446_ADVERSE_STATE_FILE") or os.getenv("V244_ADVERSE_STATE_FILE") or os.path.join("data", "execution", "v2446_adverse_steps_state.json")

def _envb(n, d=False):
    v = os.getenv(n)
    return d if v is None else str(v).strip().lower() in ("1", "true", "yes", "on", "y")

def _envf(n, d):
    try:
        return float(os.getenv(n, str(d)))
    except Exception:
        return float(d)

def _asset():
    return (os.getenv("V244_TRADED_ASSET") or "ETHUSD").upper().strip()


# === V244_PROTECTED_DEAL_IDS_ADVERSE_START ===
def _protected_deal_ids():
    raw = os.getenv("V244_PROTECTED_DEAL_IDS", "")
    return set(x.strip() for x in raw.replace(";", ",").split(",") if x.strip())

def _deal_id(o):
    if not isinstance(o, dict):
        return None
    for k in ("dealId", "deal_id", "id"):
        v = o.get(k)
        if v:
            return str(v)
    for k in ("position", "deal", "confirm", "info"):
        child = o.get(k)
        if isinstance(child, dict):
            v = _deal_id(child)
            if v:
                return v
    return None

def _is_protected_position(o):
    did = _deal_id(o)
    return bool(did) and did in _protected_deal_ids()
# === V244_PROTECTED_DEAL_IDS_ADVERSE_END ===

def _enabled():
    return _envb("V244_ADVERSE_PRICE_STEPS_ENABLED", True) and os.getenv("V244_ENTRY_MODE", "").upper().strip() == "ADVERSE_PRICE_STEPS"

def _audit(ev, **kw):
    ts = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    parts = [f"ts_utc={ts}", f"event={ev}"]
    for k, v in kw.items():
        parts.append(f"{k}={repr(v) if isinstance(v, (dict, list, tuple)) else v}")
    line = " | ".join(parts)
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        d = os.path.join("logs", "v24_4_forced_audit")
        os.makedirs(d, exist_ok=True)
        fs = glob.glob(os.path.join(d, "V24_4_FORCED_AUDIT_*.log"))
        path = max(fs, key=os.path.getmtime) if fs else os.path.join(d, "V24_4_FORCED_AUDIT_v2446_patch.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def _read():
    try:
        with open(STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write(s):
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(s, f, sort_keys=True, indent=2)
    except Exception as e:
        _audit("RUNNER_ADVERSE_STEP_STATE_WRITE_FAILED", error=repr(e))

def _num(v):
    try:
        return None if v is None else float(v)
    except Exception:
        return None

def _items(raw):
    if raw is None:
        return []
    if isinstance(raw, tuple) and len(raw) > 1:
        raw = raw[1]
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for k in ("positions", "open_positions", "data", "items"):
            if isinstance(raw.get(k), list):
                return raw[k]
        return [raw] if ("position" in raw or "epic" in raw) else []
    return []

def _norm(x):
    if not isinstance(x, dict):
        return None
    raw = x.get("raw") if isinstance(x.get("raw"), dict) else {}
    pos = x.get("position") if isinstance(x.get("position"), dict) else {}
    if not pos and isinstance(raw.get("position"), dict):
        pos = raw.get("position")
    market = x.get("market") if isinstance(x.get("market"), dict) else {}
    if not market and isinstance(raw.get("market"), dict):
        market = raw.get("market")
    p0 = pos or x
    return {
        "epic": (x.get("epic") or p0.get("epic") or market.get("epic") or "").upper(),
        "direction": (x.get("direction") or p0.get("direction") or "").upper(),
        "level": _num(x.get("level") or p0.get("level")),
        "bid": _num(market.get("bid")),
        "offer": _num(market.get("offer")),
        "dealId": _deal_id(x),
        "deal_id": _deal_id(x),
    }

def _positions(headers=None):
    # V2446E : lire les positions avec headers quand le runner les fournit.
    # Le runner expose notamment :
    # - asset_positions(headers, asset)
    # - all_positions(headers)
    # - get_positions_raw(headers)
    a = _asset()

    candidates = []

    fn = G.get("asset_positions")
    if callable(fn) and headers is not None:
        try:
            candidates.append(fn(headers, a))
        except Exception as e:
            _audit("RUNNER_ADVERSE_STEP_POSITIONS_ASSET_POSITIONS_FAILED", error=repr(e))

    fn = G.get("all_positions")
    if callable(fn) and headers is not None:
        try:
            candidates.append(fn(headers))
        except Exception as e:
            _audit("RUNNER_ADVERSE_STEP_POSITIONS_ALL_POSITIONS_FAILED", error=repr(e))

    fn = G.get("get_positions_raw")
    if callable(fn) and headers is not None:
        try:
            candidates.append(fn(headers))
        except Exception as e:
            _audit("RUNNER_ADVERSE_STEP_POSITIONS_GET_RAW_FAILED", error=repr(e))

    # Fallback ancien mode sans headers
    for n in ("get_open_positions", "get_positions", "api_get_positions", "fetch_positions"):
        fn = G.get(n)
        if callable(fn):
            try:
                candidates.append(fn())
            except Exception:
                pass

    for raw in candidates:
        out = [p for p in (_norm(i) for i in _items(raw)) if p]
        if out:
            _audit("RUNNER_ADVERSE_STEP_POSITIONS_SEEN", asset=a, count=len(out), positions=out[:5])
            return out

    _audit("RUNNER_ADVERSE_STEP_POSITIONS_EMPTY", asset=a, headers_present=bool(headers))
    return []

def _cur(side, ps):
    for p in reversed(ps):
        if side == "SELL" and p.get("bid") is not None:
            return p["bid"]
        if side == "BUY" and p.get("offer") is not None:
            return p["offer"]
        if p.get("level") is not None:
            return p["level"]
    return None

def _req(args, kwargs):
    asset0 = side = size = headers = None

    # V2446G :
    # Le runner peut appeler open_market_netting_safe soit en positionnel :
    #   open_market_netting_safe(headers, side, size, signal, state)
    # soit en nomme :
    #   open_market_netting_safe(headers=headers, side=..., size=..., signal=..., state=...)
    if isinstance(kwargs, dict):
        for hk in ("headers", "h", "auth_headers", "broker_headers"):
            if isinstance(kwargs.get(hk), dict):
                headers = kwargs.get(hk)
                break

    if headers is None and args and isinstance(args[0], dict):
        headers = args[0]

    def scan(d):
        nonlocal asset0, side, size, headers
        if isinstance(d, dict):
            # Si un sous-dictionnaire contient les headers, on les récupère aussi.
            if headers is None:
                for hk in ("headers", "h", "auth_headers", "broker_headers"):
                    if isinstance(d.get(hk), dict):
                        headers = d.get(hk)
                        break

            payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            signal = d.get("signal") if isinstance(d.get("signal"), dict) else {}

            for src in (d, payload, signal):
                asset0 = asset0 or src.get("asset") or src.get("epic") or src.get("symbol")
                side = side or src.get("side") or src.get("direction") or src.get("bias")
                size = size or src.get("size")

    scan(kwargs)

    for a in args:
        scan(a)
        if isinstance(a, str):
            u = a.upper()
            if u in ("BUY", "SELL"):
                side = side or u
            elif "USD" in u:
                asset0 = asset0 or u
        elif isinstance(a, (int, float)) and size is None:
            size = a

    _audit(
        "RUNNER_ADVERSE_STEP_REQ_PARSED",
        asset=(asset0 or _asset()).upper(),
        side=(side or "").upper(),
        size=size,
        headers_present=bool(headers),
        arg_count=len(args),
        kw_keys=sorted(list(kwargs.keys())) if isinstance(kwargs, dict) else [],
    )

    return {
        "asset": (asset0 or _asset()).upper(),
        "side": (side or "").upper(),
        "size": size,
        "headers": headers,
    }

def _seed(side, ps):
    lv = [p["level"] for p in ps if p.get("level") is not None]
    if not lv:
        return None
    return max(lv) if side == "SELL" else min(lv)

def _gate(r):
    a, s = _asset(), r.get("side")
    configured_step = _envf("V244_PRICE_STEP_POINTS", 0.0)
    min_effective_step = _envf("V244_MIN_EFFECTIVE_STEP_POINTS", 0.0)
    spread_step_mult = _envf("V244_SPREAD_STEP_MULT", 0.0)
    step = max(configured_step, min_effective_step)

    # Positions broker vues par le patch. On conserve la liste brute pour juger
    # la credibilite de la lecture, puis on filtre strictement ETHUSD.
    all_ps = _positions(r.get("headers")) or []
    ps = []
    for p0 in [p for p in all_ps if p.get("epic") == a]:
        if _is_protected_position(p0):
            _audit("RUNNER_ADVERSE_STEP_POSITION_IGNORED_PROTECTED_DEAL", asset=a, dealId=_deal_id(p0))
            continue
        ps.append(p0)
    same = [p for p in ps if p.get("direction") == s]
    c = _cur(s, ps)

    spreads = []
    for p0 in ps:
        bid0 = _num(p0.get("bid"))
        offer0 = _num(p0.get("offer"))
        if bid0 is not None and offer0 is not None and offer0 >= bid0:
            spreads.append(offer0 - bid0)
    avg_spread = (sum(spreads) / len(spreads)) if spreads else None
    spread_step = avg_spread * spread_step_mult if avg_spread is not None else None
    if spread_step is not None:
        step = max(step, spread_step)
        _audit(
            "RUNNER_ADVERSE_STEP_EFFECTIVE_STEP",
            asset=a,
            configured_step=configured_step,
            min_effective_step=min_effective_step,
            avg_spread=round(avg_spread, 5),
            spread_step_mult=spread_step_mult,
            effective_step=round(step, 5),
        )

    step_pct = _envf("V2446I_STEP_PCT", 0.0007)
    if c is not None and step_pct > 0:
        previous_step = step
        step = abs(float(c)) * step_pct
        _audit(
            "RUNNER_V2446I_DYNAMIC_STEP",
            asset=a,
            side=s,
            current_level=c,
            step_pct=step_pct,
            previous_step=previous_step,
            dynamic_step=step,
        )

    # Etat persistant V2446 : c'est notre garde-fou dur.
    st = _read()
    state_side = str(st.get("side") or "").upper()
    state_last = _num(st.get("last_step_level"))
    state_fill = _num(st.get("last_real_fill_level"))
    state_has_basket = state_last is not None or state_fill is not None
    last = state_last if state_side == s else None

    if ps and st.get("eth_empty_confirmations"):
        st2 = dict(st)
        for k in ("eth_empty_confirmations", "eth_empty_confirm_required", "eth_empty_confirm_since"):
            st2.pop(k, None)
        st2["updated_ts"] = time.time()
        _write(st2)
        st = st2
        _audit("RUNNER_ETH_EMPTY_RESET_ABORTED_POSITIONS_REAPPEARED", asset=a, side=s, open_positions=len(ps))
        _audit("RUNNER_ETH_EMPTY_RESET_CONFIRMATION_CLEARED", asset=a, side=s, open_positions=len(ps))

    # Si ETH est vide mais qu'un panier existe dans le state, on ne reset pas
    # sur une seule lecture. Il faut confirmer le vide sur plusieurs boucles.
    if not ps and state_has_basket:
        confirmations = int(_num(st.get("eth_empty_confirmations")) or 0) + 1
        required = int(_envf("V244_EMPTY_RESET_CONFIRMATIONS", 2))
        if len(all_ps) == 0:
            required = max(required, int(_envf("V244_EMPTY_RESET_CONFIRMATIONS_EMPTY_ALL", 3)))
            _audit(
                "RUNNER_ETH_EMPTY_RESET_SUSPICIOUS_BROKER_EMPTY",
                asset=a,
                side=s,
                confirmations=confirmations,
                required=required,
                all_positions_count=len(all_ps),
                state=st,
            )

        if confirmations < required:
            st2 = dict(st)
            st2.update({
                "eth_empty_confirmations": confirmations,
                "eth_empty_confirm_required": required,
                "eth_empty_confirm_since": st.get("eth_empty_confirm_since") or time.time(),
                "updated_ts": time.time(),
            })
            _write(st2)
            _audit(
                "RUNNER_ETH_EMPTY_RESET_PENDING_CONFIRMATION",
                asset=a,
                side=s,
                confirmations=confirmations,
                required=required,
                all_positions_count=len(all_ps),
                eth_positions_count=len(ps),
                state=st,
            )
            return False, {
                "reason": "ETH_EMPTY_STATE_RESET_PENDING_CONFIRMATION",
                "confirmations": confirmations,
                "required": required,
                "last_step_level": state_last,
                "step": step,
            }

        _write({
            "side": s,
            "last_step_level": None,
            "last_real_fill_level": None,
            "updated_ts": time.time(),
            "first_open_armed": True,
            "reset_reason": "BROKER_ETH_EMPTY_CONFIRMED",
            "eth_empty_confirmations": confirmations,
        })
        _audit(
            "RUNNER_ETH_EMPTY_CONFIRMED_STATE_RESET",
            asset=a,
            side=s,
            confirmations=confirmations,
            required=required,
            all_positions_count=len(all_ps),
            previous_state=st,
        )
        _audit(
            "RUNNER_ADVERSE_STEP_DECISION",
            asset=a,
            side=s,
            allow=True,
            reason="FIRST_OPEN_NO_ETH_POSITIONS_AND_CONFIRMED_STATE_RESET",
            current_level=c,
            step=step,
        )
        return True, {
            "reason": "FIRST_OPEN_NO_ETH_POSITIONS_AND_CONFIRMED_STATE_RESET",
            "current_level": c,
            "target_level": c,
        }

    # Première ouverture uniquement si aucune position n'est vue ET aucun panier précédent n'existe.
    if not ps and not state_has_basket:
        _write({"side": s, "last_step_level": None, "updated_ts": time.time(), "first_open_armed": True})
        _audit(
            "RUNNER_ADVERSE_STEP_DECISION",
            asset=a,
            side=s,
            allow=True,
            reason="FIRST_OPEN_NO_ETH_POSITIONS_AND_NO_STATE",
            current_level=c,
            step=step,
        )
        return True, {"reason": "FIRST_OPEN_NO_ETH_POSITIONS_AND_NO_STATE", "current_level": c, "target_level": c}

    # Si des positions existent mais aucun état n'est encore exploitable, on seed depuis les niveaux broker.
    if last is None:
        last = _seed(s, same or ps)
        _write({"side": s, "last_step_level": last, "updated_ts": time.time(), "seeded": True})

    if c is None or last is None:
        _audit("RUNNER_ADVERSE_STEP_BLOCKED_NO_PRICE", asset=a, side=s, current_level=c, last_step_level=last, open_positions=len(ps))
        return False, {"reason": "NO_PRICE_OR_LAST_LEVEL", "current_level": c, "last_step_level": last}

    target = last + step if s == "SELL" else last - step
    allow = c >= target if s == "SELL" else c <= target

    _audit(
        "RUNNER_ADVERSE_STEP_DECISION",
        asset=a,
        side=s,
        allow=allow,
        current_level=c,
        last_step_level=last,
        target_level=target,
        step=step,
        open_positions=len(ps),
    )

    if not allow:
        _audit("RUNNER_ADVERSE_STEP_BLOCKED_WAIT_NEXT_LEVEL", asset=a, side=s, current_level=c, target_level=target, last_step_level=last)
        return False, {"reason": "WAIT_NEXT_ADVERSE_LEVEL", "current_level": c, "target_level": target, "last_step_level": last}


    # ==========================================================
    # 🚀 PATCH PANIER CROSS-HEDGE : BIFURCATION L4 SUR US100 🚀
    # ==========================================================
    if len(ps) >= 3:
        _audit("RUNNER_CROSS_HEDGE_TRIGGER", msg="L3 plein. Blocage US500 et exécution Hedge US100.", open_positions=len(ps))
        
        hedge_asset = "US100"
        hedge_side = "SELL" if s == "BUY" else "BUY"
        hedge_size = 0.08
        
        import inspect, requests
        frame = inspect.currentframe()
        headers = frame.f_back.f_locals.get('headers') or frame.f_locals.get('kwargs', {}).get('headers') or frame.f_locals.get('headers')
        
        if headers:
            try:
                url_price = f"https://demo-api-capital.backend-capital.com/api/v1/markets/{hedge_asset}"
                res_price = requests.get(url_price, headers=headers, timeout=5).json()
                hedge_price = res_price['snapshot']['offer'] if hedge_side == "BUY" else res_price['snapshot']['bid']
                
                sl = hedge_price - 150 if hedge_side == "BUY" else hedge_price + 150
                
                url_pos = "https://demo-api-capital.backend-capital.com/api/v1/positions"
                payload = {
                    "epic": hedge_asset,
                    "direction": hedge_side,
                    "size": hedge_size,
                    "orderType": "MARKET",
                    "guaranteedStop": True,
                    "stopLevel": round(sl, 2),
                    "forceOpen": True
                }
                res = requests.post(url_pos, json=payload, headers=headers, timeout=5)
                _audit("RUNNER_CROSS_HEDGE_EXECUTED", payload=payload, status=res.status_code, response=res.text)
            except Exception as e:
                _audit("RUNNER_CROSS_HEDGE_ERROR", error=str(e))
        else:
            _audit("RUNNER_CROSS_HEDGE_ERROR", error="Headers API introuvables.")
        
        return False, {"reason": "HEDGE_L4_EXECUTED_NO_MORE_US500", "current_level": c, "target_level": target}
    # ==========================================================
    _audit("RUNNER_ADVERSE_STEP_OPEN_ALLOWED", asset=a, side=s, current_level=c, target_level=target, last_step_level=last)
    return True, {"reason": "ADVERSE_LEVEL_REACHED", "current_level": c, "target_level": target, "last_step_level": last}

def _find_level(o):
    if isinstance(o, tuple) and len(o) > 1:
        return _find_level(o[1])
    if isinstance(o, dict):
        for k in ("level", "dealLevel", "fillLevel", "openLevel"):
            v = _num(o.get(k))
            if v is not None:
                return v
        for k in ("position", "confirm", "deal", "info"):
            v = _find_level(o.get(k))
            if v is not None:
                return v
    return None

def _okinfo(res):
    if isinstance(res, tuple):
        return bool(res[0]), res[1] if len(res) > 1 else None
    if isinstance(res, dict):
        return bool(res.get("ok") or res.get("dealStatus") == "ACCEPTED" or res.get("status") in ("OPEN", "ACCEPTED")), res
    return bool(res), res

def _after(r, gate, res):
    ok, info = _okinfo(res)
    if not ok:
        return
    fill = _find_level(info)
    new = gate.get("target_level") or fill or gate.get("current_level")
    if new is not None:
        _write({"side": r.get("side"), "last_step_level": float(new), "last_real_fill_level": fill, "updated_ts": time.time()})
        _audit("RUNNER_ADVERSE_STEP_STATE_UPDATED", asset=_asset(), side=r.get("side"), last_step_level=new, fill_level=fill)

def _wrap_name(name):
    n = str(name).lower()
    if n.startswith("_v2446"):
        return False

    if n == "open_market_netting_safe":
        return True

    blocked = ("close", "cancel", "delete", "positions", "fetch", "get_", "audit", "log", "margin", "rate", "basket")
    if any(b in n for b in blocked):
        return False

    openish = any(k in n for k in ("open", "create", "place", "submit"))
    tradeish = any(k in n for k in ("position", "order", "deal", "trade", "market"))
    return openish and tradeish

def _wrap(fn, label):
    if getattr(fn, "_v2446_wrapped", False):
        return fn

    @functools.wraps(fn)
    def w(*args, **kwargs):
        global BUSY
        if not _enabled() or BUSY:
            return fn(*args, **kwargs)

        r = _req(args, kwargs)

        if r["asset"] != _asset() or r["side"] not in ("BUY", "SELL"):
            return fn(*args, **kwargs)

        ok, gate = _gate(r)

        if not ok:
            return False, {
                "stage": "ADVERSE_PRICE_STEP_BLOCKED",
                "reason": gate.get("reason"),
                "gate": gate,
            }

        BUSY = True
        try:
            res = fn(*args, **kwargs)
        finally:
            BUSY = False

        _after(r, gate, res)
        return res

    w._v2446_wrapped = True
    return w

def install(g):
    global G
    G = g
    names = []

    for name, obj in list(g.items()):
        if callable(obj) and _wrap_name(name):
            g[name] = _wrap(obj, name)
            names.append(name)

    for cname, cls in list(g.items()):
        if isinstance(cls, type):
            for attr, raw in list(cls.__dict__.items()):
                base = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
                if callable(base) and _wrap_name(attr):
                    wrapped = _wrap(base, f"{cname}.{attr}")
                    if isinstance(raw, staticmethod):
                        wrapped = staticmethod(wrapped)
                    elif isinstance(raw, classmethod):
                        wrapped = classmethod(wrapped)
                    setattr(cls, attr, wrapped)
                    names.append(f"{cname}.{attr}")

    _audit(
        "RUNNER_V2446_ADVERSE_STEP_PATCH_ACTIVE",
        entry_mode=os.getenv("V244_ENTRY_MODE"),
        step=_envf("V244_PRICE_STEP_POINTS", 0.0),
        wrapped_count=len(names),
        wrapped=names[:30],
    )
