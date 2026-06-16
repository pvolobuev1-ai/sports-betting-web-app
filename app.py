import os
import copy
import requests
import pandas as pd
import streamlit as st
from openai import OpenAI


# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================

st.set_page_config(
    page_title="AI Betting Analyst",
    page_icon="🏆",
    layout="wide"
)

st.title("🏆 AI Betting Analyst")
st.caption("Стабильная версия: коэффициенты + локальный анализ + дополнительный AI-анализ")


# ============================================================
# СЕКРЕТНЫЕ КЛЮЧИ
# ============================================================

def get_secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)


OPENAI_API_KEY = get_secret("OPENAI_API_KEY", "")
ODDS_API_KEY = get_secret("ODDS_API_KEY", "")
OPENAI_MODEL = get_secret("OPENAI_MODEL", "gpt-5.4-mini")

if not ODDS_API_KEY:
    st.error("Не найден ODDS_API_KEY. Добавь ключ The Odds API в Streamlit Secrets.")
    st.stop()

client = None

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# РЫНКИ
# ============================================================

MARKET_LABELS = {
    "Исход матча / победитель": "h2h",
    "Исход с ничьей / 1X2": "h2h_3_way",
    "Двойной шанс / команда не проиграет": "double_chance",
    "Исход без ничьей": "draw_no_bet",
    "Фора": "spreads",
    "Тотал матча": "totals",
    "ОБЗ / обе забьют": "btts",
    "Индивидуальные тоталы команд": "team_totals",
    "Расширенные тоталы матча": "alternate_totals",
    "Расширенные форы": "alternate_spreads",
    "Расширенные индивидуальные тоталы": "alternate_team_totals",

    "Угловые — тотал": "alternate_totals_corners",
    "Угловые — фора": "alternate_spreads_corners",
    "Карточки — тотал": "alternate_totals_cards",
    "Карточки — фора": "alternate_spreads_cards",

    "Тотал 1-го тайма": "totals_h1",
    "Фора 1-го тайма": "spreads_h1",
    "Исход 1-го тайма": "h2h_h1",
    "Индивидуальный тотал 1-го тайма": "team_totals_h1",

    "Хоккей — исход 1-го периода": "h2h_p1",
    "Хоккей — тотал 1-го периода": "totals_p1",
    "Хоккей — фора 1-го периода": "spreads_p1",

    "Игрок — удары": "player_shots",
    "Игрок — удары в створ": "player_shots_on_target",
    "Игрок — гол в любое время": "player_goal_scorer_anytime",
    "Игрок — карточка": "player_to_receive_card",
}


MARKET_NAMES_RU = {
    "h2h": "Исход матча / победитель",
    "h2h_3_way": "Исход с ничьей / 1X2",
    "double_chance": "Двойной шанс",
    "draw_no_bet": "Исход без ничьей",
    "spreads": "Фора",
    "totals": "Тотал матча",
    "btts": "Обе забьют",
    "team_totals": "Индивидуальные тоталы команд",
    "alternate_totals": "Расширенные тоталы матча",
    "alternate_spreads": "Расширенные форы",
    "alternate_team_totals": "Расширенные индивидуальные тоталы",
    "alternate_totals_corners": "Угловые — тотал",
    "alternate_spreads_corners": "Угловые — фора",
    "alternate_totals_cards": "Карточки — тотал",
    "alternate_spreads_cards": "Карточки — фора",
    "totals_h1": "Тотал 1-го тайма",
    "spreads_h1": "Фора 1-го тайма",
    "h2h_h1": "Исход 1-го тайма",
    "team_totals_h1": "Индивидуальный тотал 1-го тайма",
    "h2h_p1": "Хоккей — исход 1-го периода",
    "totals_p1": "Хоккей — тотал 1-го периода",
    "spreads_p1": "Хоккей — фора 1-го периода",
    "player_shots": "Игрок — удары",
    "player_shots_on_target": "Игрок — удары в створ",
    "player_goal_scorer_anytime": "Игрок — гол в любое время",
    "player_to_receive_card": "Игрок — карточка",
}


DEFAULT_MARKETS = [
    "Исход матча / победитель",
    "Фора",
    "Тотал матча",
    "ОБЗ / обе забьют",
    "Двойной шанс / команда не проиграет",
    "Исход без ничьей",
    "Индивидуальные тоталы команд",
]


# ============================================================
# THE ODDS API
# ============================================================

@st.cache_data(ttl=300)
def fetch_sports():
    url = "https://api.the-odds-api.com/v4/sports/"
    params = {
        "apiKey": ODDS_API_KEY
    }

    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(f"Ошибка загрузки видов спорта: {response.status_code} — {response.text}")

    return response.json()


@st.cache_data(ttl=180)
def fetch_events(sport_key: str):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events"
    params = {
        "apiKey": ODDS_API_KEY,
        "dateFormat": "iso"
    }

    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(f"Ошибка загрузки событий: {response.status_code} — {response.text}")

    return response.json()


@st.cache_data(ttl=120)
def fetch_event_odds(sport_key: str, event_id: str, regions: str, market_key: str):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": market_key,
        "oddsFormat": "decimal",
        "dateFormat": "iso"
    }

    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(f"{response.status_code} — {response.text}")

    return response.json()


def merge_event_odds(target_event: dict, source_event: dict):
    if not source_event:
        return target_event

    if "bookmakers" not in target_event:
        target_event["bookmakers"] = []

    target_books = target_event["bookmakers"]
    source_books = source_event.get("bookmakers", [])

    for source_book in source_books:
        source_key = source_book.get("key")
        existing_book = None

        for book in target_books:
            if book.get("key") == source_key:
                existing_book = book
                break

        if existing_book is None:
            target_books.append(copy.deepcopy(source_book))
            continue

        if "markets" not in existing_book:
            existing_book["markets"] = []

        existing_market_keys = {
            market.get("key")
            for market in existing_book.get("markets", [])
        }

        for market in source_book.get("markets", []):
            market_key = market.get("key")

            if market_key not in existing_market_keys:
                existing_book["markets"].append(copy.deepcopy(market))
                existing_market_keys.add(market_key)

    return target_event


def load_event_with_markets(sport_key: str, event: dict, regions: str, market_keys: list):
    event_id = event.get("id")

    combined_event = {
        "id": event.get("id"),
        "sport_key": event.get("sport_key"),
        "sport_title": event.get("sport_title"),
        "commence_time": event.get("commence_time"),
        "home_team": event.get("home_team"),
        "away_team": event.get("away_team"),
        "bookmakers": []
    }

    warnings = []

    if not event_id:
        warnings.append("У события нет ID.")
        return combined_event, warnings

    for market_key in market_keys:
        try:
            one_market_event = fetch_event_odds(
                sport_key=sport_key,
                event_id=event_id,
                regions=regions,
                market_key=market_key
            )

            combined_event = merge_event_odds(combined_event, one_market_event)

        except Exception:
            warnings.append(
                f"Рынок `{market_key}` недоступен для матча "
                f"{event.get('home_team')} — {event.get('away_team')}."
            )

    return combined_event, warnings


# ============================================================
# ПРЕОБРАЗОВАНИЕ ДАННЫХ
# ============================================================

def extract_bookmakers(events: list):
    bookmakers = set()

    for event in events:
        for bookmaker in event.get("bookmakers", []):
            title = bookmaker.get("title")
            if title:
                bookmakers.add(title)

    return sorted(bookmakers)


def count_markets(event: dict):
    total = 0

    for bookmaker in event.get("bookmakers", []):
        total += len(bookmaker.get("markets", []))

    return total


def make_preview_table(events: list):
    rows = []

    for event in events:
        rows.append({
            "Матч": f"{event.get('home_team')} — {event.get('away_team')}",
            "Начало": event.get("commence_time"),
            "Букмекеров": len(event.get("bookmakers", [])),
            "Рынков": count_markets(event)
        })

    return pd.DataFrame(rows)


def flatten_odds(events: list, bookmaker_choice: str):
    rows = []

    for event in events:
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        match_name = f"{home_team} — {away_team}"
        commence_time = event.get("commence_time", "")

        for bookmaker in event.get("bookmakers", []):
            bookmaker_title = bookmaker.get("title", "")

            if bookmaker_choice != "Все" and bookmaker_title != bookmaker_choice:
                continue

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                market_name = MARKET_NAMES_RU.get(market_key, market_key)

                for outcome in market.get("outcomes", []):
                    price = outcome.get("price")
                    point = outcome.get("point")
                    name = outcome.get("name", "")
                    description = outcome.get("description", "")

                    if price is None:
                        continue

                    try:
                        price = float(price)
                    except Exception:
                        continue

                    rows.append({
                        "match": match_name,
                        "time": commence_time,
                        "bookmaker": bookmaker_title,
                        "market_key": market_key,
                        "market": market_name,
                        "outcome": name,
                        "description": description,
                        "point": point,
                        "odds": price
                    })

    return pd.DataFrame(rows)


def format_bet_name(row):
    desc = row.get("description", "")
    point = row.get("point", None)

    text = f"{row['outcome']}"

    if desc:
        text += f" | {desc}"

    if pd.notna(point):
        text += f" {point}"

    return text


# ============================================================
# БАНК И РИСК
# ============================================================

def get_daily_risk_percent(risk_mode: str) -> float:
    if risk_mode == "осторожный":
        return 0.07
    if risk_mode == "умеренный":
        return 0.10
    return 0.15


def get_bankroll_plan(bankroll: float, risk_mode: str):
    daily_percent = get_daily_risk_percent(risk_mode)

    return {
        "daily_limit": round(bankroll * daily_percent, 2),
        "single_low": round(bankroll * 0.02, 2),
        "single_medium": round(bankroll * 0.04, 2),
        "single_high": round(bankroll * 0.06, 2),
        "express": round(bankroll * 0.015, 2)
    }


def stake_for_score(score: float, bankroll_plan: dict):
    if score >= 8:
        return bankroll_plan["single_high"], "повышенный"
    if score >= 6:
        return bankroll_plan["single_medium"], "средний"
    return bankroll_plan["single_low"], "низкий"


# ============================================================
# ЛОКАЛЬНЫЙ АНАЛИЗ БЕЗ OPENAI
# ============================================================

def score_market(row):
    odds = row["odds"]
    market_key = row["market_key"]

    score = 0

    if 1.45 <= odds <= 1.75:
        score += 5
    elif 1.76 <= odds <= 2.05:
        score += 4
    elif 1.30 <= odds < 1.45:
        score += 2
    elif 2.06 <= odds <= 2.40:
        score += 2
    else:
        score -= 2

    safer_markets = [
        "double_chance",
        "draw_no_bet",
        "team_totals",
        "totals",
        "spreads",
        "btts"
    ]

    stat_markets = [
        "alternate_totals_corners",
        "alternate_spreads_corners",
        "alternate_totals_cards",
        "alternate_spreads_cards"
    ]

    if market_key in safer_markets:
        score += 3

    if market_key in stat_markets:
        score += 2

    if "alternate" in market_key:
        score += 1

    return score


def local_analysis(df: pd.DataFrame, bankroll: float, risk_mode: str):
    bankroll_plan = get_bankroll_plan(bankroll, risk_mode)

    if df.empty:
        return "Нет коэффициентов для анализа."

    work = df.copy()
    work["score"] = work.apply(score_market, axis=1)

    # Фильтр: не берём слишком низкие и слишком высокие коэффициенты
    work = work[
        (work["odds"] >= 1.30) &
        (work["odds"] <= 2.40)
    ]

    if work.empty:
        return "После фильтрации не осталось подходящих коэффициентов."

    work = work.sort_values(
        by=["score", "odds"],
        ascending=[False, True]
    )

    singles = []
    used_matches = set()
    used_market_groups = set()

    for _, row in work.iterrows():
        match_name = row["match"]
        market_key = row["market_key"]

        # Не берём слишком много ставок из одного матча
        if match_name in used_matches:
            continue

        # Разнообразим рынки
        group_key = market_key.replace("alternate_", "")

        if group_key in used_market_groups and len(singles) >= 3:
            continue

        score = row["score"]

        if score < 4:
            continue

        stake, risk = stake_for_score(score, bankroll_plan)

        singles.append({
            "match": match_name,
            "market": row["market"],
            "bet": format_bet_name(row),
            "odds": row["odds"],
            "stake": stake,
            "risk": risk,
            "score": score,
            "bookmaker": row["bookmaker"]
        })

        used_matches.add(match_name)
        used_market_groups.add(group_key)

        if len(singles) >= 5:
            break

    # Экспресс: только 2 события, не больше
    express_candidates = []

    for _, row in work.iterrows():
        if 1.35 <= row["odds"] <= 1.75 and row["score"] >= 5:
            if row["match"] not in [item["match"] for item in express_candidates]:
                express_candidates.append({
                    "match": row["match"],
                    "market": row["market"],
                    "bet": format_bet_name(row),
                    "odds": row["odds"]
                })

        if len(express_candidates) >= 2:
            break

    total_single_stake = sum(item["stake"] for item in singles)
    express_stake = bankroll_plan["express"] if len(express_candidates) >= 2 else 0
    total_risk = total_single_stake + express_stake
    total_risk_percent = round((total_risk / bankroll) * 100, 2)

    lines = []

    lines.append("# ✅ Локальный анализ")
    lines.append("")
    lines.append(f"Банк: **{bankroll}**")
    lines.append(f"Режим риска: **{risk_mode}**")
    lines.append(f"Лимит риска на день: **{bankroll_plan['daily_limit']}**")
    lines.append("")

    lines.append("## Рекомендуемые ординары")
    lines.append("")

    if not singles:
        lines.append("Подходящих ординаров не найдено. Лучше пропустить линию или выбрать меньше рискованные рынки.")
    else:
        for index, bet in enumerate(singles, start=1):
            lines.append(f"### {index}. {bet['match']}")
            lines.append(f"- Букмекер: **{bet['bookmaker']}**")
            lines.append(f"- Рынок: **{bet['market']}**")
            lines.append(f"- Ставка: **{bet['bet']}**")
            lines.append(f"- Коэффициент: **{bet['odds']}**")
            lines.append(f"- Сумма: **{bet['stake']}**")
            lines.append(f"- Риск: **{bet['risk']}**")
            lines.append(f"- Оценка алгоритма: **{bet['score']}/10**")
            lines.append("")

    lines.append("## Экспресс")
    lines.append("")

    if len(express_candidates) >= 2:
        total_odds = 1

        for item in express_candidates:
            total_odds *= item["odds"]

        total_odds = round(total_odds, 2)

        lines.append(f"Сумма экспресса: **{express_stake}**")
        lines.append(f"Примерный общий коэффициент: **{total_odds}**")
        lines.append("")

        for item in express_candidates:
            lines.append(f"- **{item['match']}** — {item['market']} — {item['bet']} за {item['odds']}")

        lines.append("")
        lines.append("Экспресс лучше держать маленьким, потому что даже 2 события сильно повышают риск.")
    else:
        lines.append("Экспресс лучше не собирать: недостаточно подходящих событий с умеренным коэффициентом.")

    lines.append("")
    lines.append("## Что лучше пропустить")
    lines.append("")
    lines.append("- Коэффициенты ниже 1.30: слишком маленькая отдача.")
    lines.append("- Коэффициенты выше 2.40: слишком высокий риск для основной стратегии.")
    lines.append("- Несколько ставок на один и тот же матч.")
    lines.append("- Рынки, которых нет в загруженной линии.")
    lines.append("")

    lines.append("## Общий риск на день")
    lines.append("")
    lines.append(f"Общая сумма ставок: **{round(total_risk, 2)}**")
    lines.append(f"Это примерно **{total_risk_percent}%** от банка.")
    lines.append("")

    if total_risk > bankroll_plan["daily_limit"]:
        lines.append("⚠️ Общий риск выше лимита. Лучше уменьшить суммы ставок.")
    else:
        lines.append("✅ Общий риск находится в пределах выбранного режима.")

    lines.append("")
    lines.append("## Важно")
    lines.append("")
    lines.append("Это не гарантия прибыли. Алгоритм отбирает рынки по коэффициентам и риску, но не знает составы, травмы и мотивацию команд.")

    return "\n".join(lines)


# ============================================================
# AI-АНАЛИЗ, КОТОРЫЙ НЕ ЛОМАЕТ ПРИЛОЖЕНИЕ
# ============================================================

def ai_analysis_safe(df: pd.DataFrame, bankroll: float, risk_mode: str):
    if client is None:
        return "OpenAI API key не найден. AI-анализ отключён."

    if df.empty:
        return "Нет данных для AI-анализа."

    sample = df.copy()
    sample["bet"] = sample.apply(format_bet_name, axis=1)
    sample["score"] = sample.apply(score_market, axis=1)

    sample = sample[
        (sample["odds"] >= 1.30) &
        (sample["odds"] <= 2.40)
    ]

    sample = sample.sort_values(
        by=["score", "odds"],
        ascending=[False, True]
    ).head(40)

    text_rows = []

    for _, row in sample.iterrows():
        text_rows.append(
            f"{row['match']} | {row['bookmaker']} | {row['market']} | "
            f"{row['bet']} | {row['odds']}"
        )

    odds_text = "\n".join(text_rows)

    prompt = f"""
Проанализируй список ставок. Не придумывай новые матчи, рынки и коэффициенты.

Банк: {bankroll}
Режим риска: {risk_mode}

Доступные варианты:
{odds_text}

Нужно:
1. Выбрать 2–5 лучших ординаров.
2. Дать маленький экспресс только если он оправдан.
3. Указать суммы ставок от банка.
4. Объяснить риск.
5. Отдельно отметить рынки: исходы, тоталы, форы, ОБЗ, индивидуальные тоталы, угловые, карточки.
6. Не обещать гарантированную прибыль.

Ответ дай на русском языке.
"""

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
            max_output_tokens=1200
        )

        return response.output_text

    except Exception as e:
        return (
            "AI-анализ временно не сработал, но локальный анализ выше остаётся рабочим.\n\n"
            f"Техническая ошибка OpenAI: `{e}`"
        )


# ============================================================
# БОКОВАЯ ПАНЕЛЬ
# ============================================================

st.sidebar.header("⚙️ Настройки")

bankroll = st.sidebar.number_input(
    "Банк",
    min_value=100.0,
    max_value=1_000_000.0,
    value=1488.0,
    step=10.0
)

risk_mode = st.sidebar.selectbox(
    "Режим риска",
    ["осторожный", "умеренный", "агрессивный"],
    index=2
)

regions = st.sidebar.selectbox(
    "Регион коэффициентов",
    ["eu", "uk", "us", "au"],
    index=0
)

max_events = st.sidebar.slider(
    "Сколько матчей загружать",
    min_value=1,
    max_value=8,
    value=2
)

use_ai = st.sidebar.checkbox(
    "Добавить AI-анализ OpenAI",
    value=False
)

st.sidebar.divider()

st.sidebar.subheader("🎯 Рынки")

selected_market_labels = st.sidebar.multiselect(
    "Выбери рынки",
    list(MARKET_LABELS.keys()),
    default=DEFAULT_MARKETS
)

custom_markets_input = st.sidebar.text_area(
    "Дополнительные market keys",
    placeholder="Например: totals_fouls,spreads_throw_ins,total_shots",
    help="Если The Odds API не поддерживает ключ, приложение просто пропустит этот рынок."
)

selected_market_keys = [
    MARKET_LABELS[label]
    for label in selected_market_labels
]

if custom_markets_input.strip():
    custom_keys = [
        item.strip()
        for item in custom_markets_input.split(",")
        if item.strip()
    ]

    selected_market_keys.extend(custom_keys)

selected_market_keys = list(dict.fromkeys(selected_market_keys))

st.sidebar.divider()

bankroll_plan = get_bankroll_plan(bankroll, risk_mode)

st.sidebar.subheader("💰 Лимиты")
st.sidebar.write(f"Лимит на день: **{bankroll_plan['daily_limit']}**")
st.sidebar.write(f"Низкая ставка: **{bankroll_plan['single_low']}**")
st.sidebar.write(f"Средняя ставка: **{bankroll_plan['single_medium']}**")
st.sidebar.write(f"Высокая ставка: **{bankroll_plan['single_high']}**")
st.sidebar.write(f"Экспресс: **{bankroll_plan['express']}**")


# ============================================================
# ОСНОВНОЙ ИНТЕРФЕЙС
# ============================================================

st.subheader("1. Выбери спорт")

try:
    sports = fetch_sports()
except Exception as e:
    st.error(str(e))
    st.stop()

active_sports = [
    sport for sport in sports
    if sport.get("active") is True
]

sport_options = {
    f"{sport.get('title')} — {sport.get('key')}": sport.get("key")
    for sport in active_sports
}

if not sport_options:
    st.error("Не удалось получить список активных видов спорта.")
    st.stop()

selected_sport_label = st.selectbox(
    "Спорт / лига",
    list(sport_options.keys())
)

selected_sport_key = sport_options[selected_sport_label]


if "loaded_events" not in st.session_state:
    st.session_state.loaded_events = []

if "load_warnings" not in st.session_state:
    st.session_state.load_warnings = []


st.subheader("2. Загрузи коэффициенты")

st.info(
    "Сначала лучше загружать 1–2 матча и 5–7 рынков. "
    "Если выбрать слишком много рынков, быстрее расходуется лимит The Odds API."
)

if st.button("🔎 Загрузить коэффициенты"):
    if not selected_market_keys:
        st.warning("Выбери хотя бы один рынок.")
    else:
        try:
            base_events = fetch_events(selected_sport_key)
            base_events = base_events[:max_events]

            loaded_events = []
            load_warnings = []

            progress = st.progress(0)

            for index, event in enumerate(base_events):
                loaded_event, warnings = load_event_with_markets(
                    sport_key=selected_sport_key,
                    event=event,
                    regions=regions,
                    market_keys=selected_market_keys
                )

                if loaded_event and count_markets(loaded_event) > 0:
                    loaded_events.append(loaded_event)

                load_warnings.extend(warnings)

                progress.progress((index + 1) / max(len(base_events), 1))

            st.session_state.loaded_events = loaded_events
            st.session_state.load_warnings = load_warnings

            if not loaded_events:
                st.warning("Коэффициенты не найдены. Попробуй другой спорт, регион или меньше рынков.")
            else:
                st.success(f"Загружено событий с коэффициентами: {len(loaded_events)}")

        except Exception as e:
            st.error(str(e))


events = st.session_state.loaded_events
load_warnings = st.session_state.load_warnings


if load_warnings:
    with st.expander("Предупреждения по рынкам"):
        for warning in load_warnings[:100]:
            st.write(f"- {warning}")


if events:
    st.subheader("3. Выбери букмекера")

    bookmakers = extract_bookmakers(events)

    if not bookmakers:
        st.warning("Букмекеры не найдены. Попробуй другой спорт или регион.")
        st.stop()

    bookmaker_choice = st.selectbox(
        "Букмекер",
        ["Все"] + bookmakers
    )

    st.subheader("4. Найденные события")

    preview_df = make_preview_table(events)
    st.dataframe(preview_df, use_container_width=True)

    df = flatten_odds(events, bookmaker_choice)

    st.subheader("5. Найденные рынки")

    if df.empty:
        st.warning("Для выбранного букмекера нет рынков. Выбери другого букмекера или вариант «Все».")
    else:
        show_df = df.copy()
        show_df["Ставка"] = show_df.apply(format_bet_name, axis=1)

        show_df = show_df[
            [
                "match",
                "bookmaker",
                "market",
                "Ставка",
                "odds"
            ]
        ]

        show_df.columns = [
            "Матч",
            "Букмекер",
            "Рынок",
            "Ставка",
            "Коэффициент"
        ]

        st.dataframe(show_df, use_container_width=True)

        st.subheader("6. Анализ ставок")

        if st.button("🧠 Проанализировать"):
            local_result = local_analysis(
                df=df,
                bankroll=bankroll,
                risk_mode=risk_mode
            )

            st.markdown(local_result)

            if use_ai:
                st.divider()
                st.subheader("Дополнительный AI-анализ")

                with st.spinner("Пробую получить AI-анализ..."):
                    ai_result = ai_analysis_safe(
                        df=df,
                        bankroll=bankroll,
                        risk_mode=risk_mode
                    )

                st.markdown(ai_result)

else:
    st.info("Сначала выбери спорт и нажми «Загрузить коэффициенты».")


# ============================================================
# НИЖНИЙ БЛОК
# ============================================================

st.divider()

st.caption(
    "Приложение не гарантирует прибыль. Локальный анализ оценивает коэффициенты и риск, "
    "но не учитывает составы, травмы, мотивацию и новости. "
    "Если нужного рынка нет в The Odds API, приложение не сможет получить его автоматически."
)
