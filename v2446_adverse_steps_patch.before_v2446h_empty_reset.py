import os, json, glob, time, functools, datetime

G = {}
BUSY = False
STATE = os.path.join("data", "execution", "v2446_adverse_steps_state.json")

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
    a, s, step = _asset(), r.get("side"), _envf("V244_PRICE_STEP_POINTS", 1.0)

    # Positions broker vues par le patch. Attention : selon la signature des fonctions du runner,
    # cette liste peut être vide même si Capital.com a déjà des positions ouvertes.
    ps = [p for p in _positions(r.get("headers")) if p.get("epic") == a]
    same = [p for p in ps if p.get("direction") == s]
    c = _cur(s, ps)

    # Etat persistant V2446 : c'est notre garde-fou dur.
    st = _read()
    state_side = str(st.get("side") or "").upper()
    last = _num(st.get("last_step_level")) if state_side == s else None

    # Si le patch ne voit pas les positions mais qu'un palier existe déjà,
    # on interdit absolument de repartir en FIRST_OPEN.
    if not ps and last is not None:
        _audit(
            "RUNNER_ADVERSE_STEP_HARD_BLOCK_NO_BROKER_POS_BUT_STATE_EXISTS",
            asset=a,
            side=s,
            current_level=c,
            last_step_level=last,
            step=step,
            state=st,
        )
        return False, {
            "reason": "NO_BROKER_POS_BUT_STATE_EXISTS_HARD_BLOCK",
            "current_level": c,
            "last_step_level": last,
            "step": step,
        }

    # Première ouverture uniquement si aucune position n'est vue ET aucun palier précédent n'existe.
    if not ps and last is None:
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
        step=_envf("V244_PRICE_STEP_POINTS", 1.0),
        wrapped_count=len(names),
        wrapped=names[:30],
    )
