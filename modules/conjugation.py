from janome.tokenizer import Tokenizer

FORMS = (
    "ます形", "ない形", "た形", "て形", "可能形", "意志形",
    "命令形", "条件形", "受身形", "使役形",
)

# ending -> (ます, ない, た, て, 可能, 意志, 命令, 条件, 受身, 使役)
_GODAN = {
    "う": ("い", "わ", "っ", "っ", "え", "お", "え", "え"),
    "く": ("き", "か", "い", "い", "け", "こ", "け", "け"),
    "ぐ": ("ぎ", "が", "い", "い", "げ", "ご", "げ", "げ"),
    "す": ("し", "さ", "し", "し", "せ", "そ", "せ", "せ"),
    "つ": ("ち", "た", "っ", "っ", "て", "と", "て", "て"),
    "る": ("り", "ら", "っ", "っ", "れ", "ろ", "れ", "れ"),
    "む": ("み", "ま", "ん", "ん", "め", "も", "め", "め"),
    "ぶ": ("び", "ば", "ん", "ん", "べ", "ぼ", "べ", "べ"),
    "ぬ": ("に", "な", "ん", "ん", "ね", "の", "ね", "ね"),
}
_VOICED_TA = {"ぐ", "む", "ぶ", "ぬ"}

_tokenizer: Tokenizer | None = None


def _tokenize(text: str):
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return list(_tokenizer.tokenize(text))


def _suru(prefix: str) -> dict[str, str]:
    return dict(zip(FORMS, (
        prefix + "します", prefix + "しない", prefix + "した", prefix + "して",
        prefix + "できる", prefix + "しよう", prefix + "しろ／せよ", prefix + "すれば",
        prefix + "される", prefix + "させる",
    )))


def _kuru(prefix: str) -> dict[str, str]:
    return dict(zip(FORMS, (
        prefix + "来ます", prefix + "来ない", prefix + "来た", prefix + "来て",
        prefix + "来られる", prefix + "来よう", prefix + "来い", prefix + "来れば",
        prefix + "来られる", prefix + "来させる",
    )))


def _ichidan(base: str) -> dict[str, str]:
    stem = base[:-1]
    return dict(zip(FORMS, (
        stem + "ます", stem + "ない", stem + "た", stem + "て", stem + "られる",
        stem + "よう", stem + "ろ", stem + "れば", stem + "られる", stem + "させる",
    )))


def _godan(base: str) -> dict[str, str]:
    stem, last = base[:-1], base[-1]
    masu, nai, ta, te, potential, volitional, imperative, conditional = _GODAN[last]
    if base.endswith("行く") or base == "いく":
        ta, te = "っ", "っ"
    ta_ending = "だ" if last in _VOICED_TA or (last == "ぐ") else "た"
    te_ending = "で" if ta_ending == "だ" else "て"
    return dict(zip(FORMS, (
        stem + masu + "ます", stem + nai + "ない", stem + ta + ta_ending,
        stem + te + te_ending, stem + potential + "る", stem + volitional + "う",
        stem + imperative, stem + conditional + "ば", stem + nai + "れる",
        stem + nai + "せる",
    )))


def conjugate(text: str) -> tuple[str, dict[str, str]] | None:
    """Return (dictionary form, forms) for a verb in any inflection, or None."""
    text = text.strip()
    if not text:
        return None
    if text.endswith("する") or text == "す":
        return text, _suru(text[:-2])
    if text.endswith("来る") or text == "くる":
        return text, _kuru(text[:-2] if text.endswith("来る") else "")

    tokens = _tokenize(text)
    for index, token in enumerate(tokens):
        if not token.part_of_speech.startswith("動詞"):
            continue
        base = token.base_form
        prefix = "".join(t.surface for t in tokens[:index])
        kind = token.infl_type
        if "サ変" in kind:
            return prefix + base, _suru(prefix + base[:-2])
        if "カ変" in kind:
            return prefix + base, _kuru(prefix + base[:-2])
        if "一段" in kind:
            return prefix + base, _ichidan(prefix + base)
        if "五段" in kind and base[-1] in _GODAN:
            return prefix + base, _godan(prefix + base)
        return None
    return None


ADJECTIVE_FORMS = (
    "丁寧形", "否定形", "過去形", "過去否定", "て形", "副詞形",
    "条件形", "たら形", "名詞化", "推量形",
)


def conjugate_adjective(text: str) -> tuple[str, str, dict[str, str]] | None:
    """Return (dictionary form, kind, forms) for an い-adjective, な-adjective or noun."""
    text = text.strip()
    if not text:
        return None
    tokens = _tokenize(text)
    if not tokens:
        return None
    first = tokens[0]
    pos = first.part_of_speech.split(",")
    if pos[0] == "形容詞":
        base = first.base_form
        if not base.endswith("い"):
            return None
        stem = base[:-1]
        if base in ("いい", "良い"):
            stem = base[:-2] + "よ" if base == "いい" else "良"
            base_for_forms = base
        else:
            base_for_forms = base
        forms = dict(zip(ADJECTIVE_FORMS, (
            base_for_forms + "です", stem + "くない", stem + "かった", stem + "くなかった",
            stem + "くて", stem + "く", stem + "ければ", stem + "かったら",
            (stem + "さ") if base_for_forms not in ("いい",) else "よさ", base_for_forms + "だろう",
        )))
        return base, "い-adjective", forms
    if pos[0] == "名詞" and len(tokens) <= 2:
        base = first.surface
        if len(tokens) == 2 and tokens[1].surface not in ("な", "だ", "に", "です", "で"):
            return None
        kind = "な-adjective / noun" if "形容動詞語幹" in pos else "Noun (+ copula)"
        forms = dict(zip(ADJECTIVE_FORMS, (
            base + "です", base + "じゃない", base + "だった", base + "じゃなかった",
            base + "で", base + "に", base + "なら", base + "だったら",
            base + "さ" if "形容動詞語幹" in pos else "—", base + "だろう",
        )))
        return base, kind, forms
    return None
