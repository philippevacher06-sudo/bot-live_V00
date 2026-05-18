# BOT_PIVOT_00D_pair_director_authority.py
# V2446 — Règle légère d'autorité directionnelle
#
# But :
# - ne pas inventer les paires directrices ;
# - utiliser celles déjà prévues dans le code ;
# - décider si un panier est aligné, en alerte, en conflit ou invalidé ;
# - interdire les renforts contre le directeur ;
# - préparer une fermeture défensive si le conflit est confirmé.

from dataclasses import dataclass
from typing import Optional, Sequence


BUY = "BUY"
SELL = "SELL"
NEUTRAL = "NEUTRAL"

ALIGNED = "ALIGNED"
WARNING = "WARNING"
CONFLICT = "CONFLICT"
INVALIDATED = "INVALIDATED"


BUY_WORDS = {
    "BUY", "LONG", "BULL", "BULLISH", "UP", "TREND_UP",
    "HAUSSIER", "HAUSSE", "ACHAT"
}

SELL_WORDS = {
    "SELL", "SHORT", "BEAR", "BEARISH", "DOWN", "TREND_DOWN",
    "BAISSIER", "BAISSE", "VENTE"
}

NEUTRAL_WORDS = {
    "WAIT", "HOLD", "IDLE", "NONE", "NEUTRAL", "RANGE",
    "FLAT", "UNKNOWN", "", None
}


def normalize_side(value) -> str:
    """
    Convertit les valeurs du bot en BUY / SELL / NEUTRAL.
    Fonction volontairement tolérante pour éviter de casser le code existant.
    """
    if value is None:
        return NEUTRAL

    v = str(value).strip().upper()

    if v in BUY_WORDS:
        return BUY

    if v in SELL_WORDS:
        return SELL

    if v in NEUTRAL_WORDS:
        return NEUTRAL

    if "BUY" in v or "BULL" in v or "UP" in v:
        return BUY

    if "SELL" in v or "BEAR" in v or "DOWN" in v:
        return SELL

    return NEUTRAL


def opposite(side: str) -> str:
    side = normalize_side(side)
    if side == BUY:
        return SELL
    if side == SELL:
        return BUY
    return NEUTRAL


def candle_structure_from_closes(
    closes: Sequence[float],
    confirm_bars: int = 2,
    epsilon: float = 0.0,
) -> str:
    """
    Lecture très légère de structure bougies à partir des derniers closes.

    Retourne :
    - BUY si les dernières variations sont majoritairement haussières ;
    - SELL si les dernières variations sont majoritairement baissières ;
    - NEUTRAL sinon.

    confirm_bars=2 signifie :
    sur les dernières variations, il faut au moins 2 confirmations dans le même sens.
    """
    if not closes or len(closes) < confirm_bars + 1:
        return NEUTRAL

    try:
        vals = [float(x) for x in closes if x is not None]
    except Exception:
        return NEUTRAL

    if len(vals) < confirm_bars + 1:
        return NEUTRAL

    recent = vals[-(confirm_bars + 1):]
    ups = 0
    downs = 0

    for prev, cur in zip(recent, recent[1:]):
        diff = cur - prev
        if diff > epsilon:
            ups += 1
        elif diff < -epsilon:
            downs += 1

    if ups >= confirm_bars:
        return BUY

    if downs >= confirm_bars:
        return SELL

    return NEUTRAL


@dataclass(frozen=True)
class AuthorityDecision:
    state: str
    basket_side: str
    director_m15: str
    director_m5: str
    traded_structure: str
    allow_entry: bool
    allow_reinforce: bool
    should_close_defensive: bool
    reason: str


def assess_pair_director_authority(
    basket_side: Optional[str],
    director_m15,
    director_m5,
    traded_structure=None,
    wanted_entry_side: Optional[str] = None,
) -> AuthorityDecision:
    """
    Règle universelle d'autorité directionnelle.

    basket_side :
    - BUY / SELL si panier ouvert ;
    - None si on évalue une nouvelle entrée.

    wanted_entry_side :
    - BUY / SELL quand on veut savoir si une entrée est autorisée.

    director_m15 :
    - direction principale du directeur déjà configuré.

    director_m5 :
    - confirmation courte du directeur déjà configuré.

    traded_structure :
    - structure récente de l'actif tradé.
    - peut rester NEUTRAL si non disponible.
    """

    bside = normalize_side(basket_side)
    m15 = normalize_side(director_m15)
    m5 = normalize_side(director_m5)
    tstruct = normalize_side(traded_structure)
    wanted = normalize_side(wanted_entry_side)

    # Cas 1 : pas de panier ouvert, on évalue une entrée.
    if bside == NEUTRAL:
        if wanted in (BUY, SELL) and m15 == wanted and m5 == wanted:
            if tstruct in (wanted, NEUTRAL):
                return AuthorityDecision(
                    state=ALIGNED,
                    basket_side=bside,
                    director_m15=m15,
                    director_m5=m5,
                    traded_structure=tstruct,
                    allow_entry=True,
                    allow_reinforce=False,
                    should_close_defensive=False,
                    reason="ENTRY_ALLOWED_DIRECTOR_ALIGNED",
                )

        return AuthorityDecision(
            state=WARNING,
            basket_side=bside,
            director_m15=m15,
            director_m5=m5,
            traded_structure=tstruct,
            allow_entry=False,
            allow_reinforce=False,
            should_close_defensive=False,
            reason="ENTRY_BLOCKED_DIRECTOR_NOT_ALIGNED",
        )

    # Cas 2 : panier ouvert.
    opp = opposite(bside)

    # Directeur pleinement aligné avec le panier.
    if m15 == bside and m5 == bside:
        if tstruct == opp:
            return AuthorityDecision(
                state=WARNING,
                basket_side=bside,
                director_m15=m15,
                director_m5=m5,
                traded_structure=tstruct,
                allow_entry=False,
                allow_reinforce=False,
                should_close_defensive=False,
                reason="WARNING_TRADED_STRUCTURE_AGAINST_BASKET",
            )

        return AuthorityDecision(
            state=ALIGNED,
            basket_side=bside,
            director_m15=m15,
            director_m5=m5,
            traded_structure=tstruct,
            allow_entry=False,
            allow_reinforce=True,
            should_close_defensive=False,
            reason="REINFORCE_ALLOWED_DIRECTOR_ALIGNED",
        )

    # Directeur pleinement opposé au panier.
    if m15 == opp and m5 == opp:
        if tstruct == opp:
            return AuthorityDecision(
                state=INVALIDATED,
                basket_side=bside,
                director_m15=m15,
                director_m5=m5,
                traded_structure=tstruct,
                allow_entry=False,
                allow_reinforce=False,
                should_close_defensive=True,
                reason="DEFENSIVE_CLOSE_DIRECTOR_CONFLICT_CONFIRMED",
            )

        return AuthorityDecision(
            state=CONFLICT,
            basket_side=bside,
            director_m15=m15,
            director_m5=m5,
            traded_structure=tstruct,
            allow_entry=False,
            allow_reinforce=False,
            should_close_defensive=False,
            reason="NO_REINFORCE_AGAINST_DIRECTOR",
        )

    # Directeur ambigu, non aligné ou M15/M5 contradictoires.
    return AuthorityDecision(
        state=WARNING,
        basket_side=bside,
        director_m15=m15,
        director_m5=m5,
        traded_structure=tstruct,
        allow_entry=False,
        allow_reinforce=False,
        should_close_defensive=False,
        reason="WARNING_DIRECTOR_NOT_CLEAR",
    )


def format_authority_log(asset: str, director_asset: str, decision: AuthorityDecision) -> str:
    """
    Ligne de log courte et lisible.
    """
    return (
        f"PAIR_DIRECTOR_AUTHORITY | asset={asset} director={director_asset} "
        f"state={decision.state} basket_side={decision.basket_side} "
        f"director_m15={decision.director_m15} director_m5={decision.director_m5} "
        f"traded_structure={decision.traded_structure} "
        f"allow_entry={decision.allow_entry} "
        f"allow_reinforce={decision.allow_reinforce} "
        f"should_close_defensive={decision.should_close_defensive} "
        f"reason={decision.reason}"
    )


if __name__ == "__main__":
    tests = [
        # Entrée BUY autorisée
        dict(asset="ETHUSD", director="BTCUSD", basket_side=None, wanted_entry_side="BUY", director_m15="BUY", director_m5="BUY", traded_structure="BUY"),

        # Entrée SELL bloquée car directeur BUY
        dict(asset="ETHUSD", director="BTCUSD", basket_side=None, wanted_entry_side="SELL", director_m15="BUY", director_m5="BUY", traded_structure="SELL"),

        # Panier SELL aligné, renfort autorisé
        dict(asset="ETHUSD", director="BTCUSD", basket_side="SELL", wanted_entry_side=None, director_m15="SELL", director_m5="SELL", traded_structure="SELL"),

        # Panier SELL, directeur BUY, structure pas encore confirmée : conflit, pas de renfort
        dict(asset="ETHUSD", director="BTCUSD", basket_side="SELL", wanted_entry_side=None, director_m15="BUY", director_m5="BUY", traded_structure="NEUTRAL"),

        # Panier SELL, directeur BUY, ETH structure BUY : invalidation, fermeture défensive
        dict(asset="ETHUSD", director="BTCUSD", basket_side="SELL", wanted_entry_side=None, director_m15="BUY", director_m5="BUY", traded_structure="BUY"),

        # Panier BUY, directeur SELL, structure SELL : invalidation, fermeture défensive
        dict(asset="ETHUSD", director="BTCUSD", basket_side="BUY", wanted_entry_side=None, director_m15="SELL", director_m5="SELL", traded_structure="SELL"),
    ]

    for t in tests:
        decision = assess_pair_director_authority(
            basket_side=t["basket_side"],
            wanted_entry_side=t["wanted_entry_side"],
            director_m15=t["director_m15"],
            director_m5=t["director_m5"],
            traded_structure=t["traded_structure"],
        )
        print(format_authority_log(t["asset"], t["director"], decision))
