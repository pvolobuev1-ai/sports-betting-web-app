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
st.caption("Поиск коэффициентов через The Odds API + анализ ставок через OpenAI")


# ============================================================
# СЕКРЕТНЫЕ КЛЮЧИ
# ============================================================

def get_secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)


OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
ODDS_API_KEY = get_secret("ODDS_API_KEY")
OPENAI_MODEL = get_secret("OPENAI_MODEL", "gpt-5.5")

if not OPENAI_API_KEY:
    st.error("Не найден OPENAI_API_KEY. Добавь ключ OpenAI в Streamlit Secrets.")
    st.stop()

if not ODDS_API_KEY:
    st.error("Не найден ODDS_API_KEY. Добавь ключ The Odds API в Streamlit Secrets.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# РЫНКИ СТАВОК
# ============================================================

MARKET_LABELS = {
    # Основные рынки
    "Исход матча / победитель / 1X2": "h2h",
    "Фора": "spreads",
    "Тотал матча": "totals",

    # Исходы с учетом ничьей
    "Исход 3-way / с ничьей": "h2h_3_way",
    "Двойной шанс / команда не проиграет": "double_chance",
    "Исход без ничьей / Draw No Bet": "draw_no_bet",

    # Голы
    "ОБЗ / обе команды забьют": "btts",
    "Индивидуальные тоталы команд": "team_totals",
    "Расширенные индивидуальные тоталы команд": "alternate_team_totals",
    "Расширенные тоталы матча": "alternate_totals",
    "Расширенные форы": "alternate_spreads",

    # Периоды / таймы
    "Исход 1-го тайма": "h2h_h1",
    "Исход 2-го тайма": "h2h_h2",
    "Исход 1-го тайма с ничьей": "h2h_3_way_h1",
    "Исход 2-го тайма с ничьей": "h2h_3_way_h2",
    "Фора 1-го тайма": "spreads_h1",
    "Фора 2-го тайма": "spreads_h2",
    "Тотал 1-го тайма": "totals_h1",
    "Тотал 2-го тайма": "totals_h2",
    "Индивидуальный тотал 1-го тайма": "team_totals_h1",
    "Индивидуальный тотал 2-го тайма": "team_totals_h2",

    # Футбольная статистика команд
    "Угловые — тотал": "alternate_totals_corners",
    "Угловые — фора": "alternate_spreads_corners",
    "Жёлтые карточки / карточки — тотал": "alternate_totals_cards",
    "Жёлтые карточки / карточки — фора": "alternate_spreads_cards",

    # Игровые периоды для хоккея
    "Хоккей — исход 1-го периода": "h2h_p1",
    "Хоккей — исход 2-го периода": "h2h_p2",
    "Хоккей — исход 3-го периода": "h2h_p3",
    "Хоккей — фора 1-го периода": "spreads_p1",
    "Хоккей — фора 2-го периода": "spreads_p2",
    "Хоккей — фора 3-го периода": "spreads_p3",
    "Хоккей — тотал 1-го периода": "totals_p1",
    "Хоккей — тотал 2-го периода": "totals_p2",
    "Хоккей — тотал 3-го периода": "totals_p3",

    # Игроки, если доступны в API
    "Игрок забьёт в любое время": "player_goal_scorer_anytime",
    "Игрок нанесёт удары": "player_shots",
    "Игрок нанесёт удары в створ": "player_shots_on_target",
    "Игрок получит карточку": "player_to_receive_card",
}


MARKET_RU_NAMES = {
    "h2h": "Исход матча / победитель / 1X2",
    "spreads": "Фора",
    "totals": "Тотал матча",
    "h2h_3_way": "Исход 3-way / с ничьей",
    "double_chance": "Двойной шанс",
    "draw_no_bet": "Исход без ничьей",
    "btts": "Обе забьют",
    "team_totals": "Индивидуальные тоталы команд",
    "alternate_team_totals": "Расширенные индивидуальные тоталы команд",
    "alternate_totals": "Расширенные тоталы",
    "alternate_spreads": "Расширенные форы",
    "h2h_h1": "Исход 1-го тайма",
    "h2h_h2": "Исход 2-го тайма",
    "h2h_3_way_h1": "Исход 1-го тайма с ничьей",
    "h2h_3_way_h2": "Исход 2-го тайма с ничьей",
    "spreads_h1": "Фора 1-го тайма",
    "spreads_h2": "Фора 2-го тайма",
    "totals_h1": "Тотал 1-го тайма",
    "totals_h2": "Тотал 2-го тайма",
    "team_totals_h1": "Индивидуальный тотал 1-го тайма",
    "team_totals_h2": "Индивидуальный тотал 2-го тайма",
    "alternate_totals_corners": "Угловые — тотал",
    "alternate_spreads_corners": "Угловые — фора",
    "alternate_totals_cards": "Карточки — тотал",
    "alternate_spreads_cards": "Карточки — фора",
    "h2h_p1": "Хоккей — исход 1-го периода",
    "h2h_p2": "Хоккей — исход 2-го периода",
    "h2h_p3": "Хоккей — исход 3-го периода",
    "spreads_p1": "Хоккей — фора 1-го периода",
    "spreads_p2": "Хоккей — фора 2-го периода",
    "spreads_p3": "Хоккей — фора 3-го периода",
    "totals_p1": "Хоккей — тотал 1-го периода",
    "totals_p2": "Хоккей — тотал 2-го периода",
    "totals_p3": "Хоккей — тотал 3-го периода",
    "player_goal_scorer_anytime": "Игрок забьёт в любое время",
    "player_shots": "Игрок нанесёт удары",
    "player_shots_on_target": "Игрок нанесёт удары в створ",
    "player_to_receive_card": "Игрок получит карточку",
}


DEFAULT_MARKETS = [
    "Исход матча / победитель / 1X2",
    "Фора",
    "Тотал матча",
    "Двойной шанс / команда не проиграет",
    "ОБЗ / обе команды забьют",
    "Индивидуальные тоталы команд",
    "Угловые — тотал",
    "Жёлтые карточки / карточки — тотал",
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
        raise Exception(
            f"Ошибка загрузки видов спорта: {response.status_code} — {response.text}"
        )

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
        raise Exception(
            f"Ошибка загрузки событий: {response.status_code} — {response.text}"
        )

    return response.json()


@st.cache_data(ttl=120)
def fetch_event_odds(sport_key: str, event_id: str, regions: str, markets: str):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso"
    }

    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(
            f"Ошибка загрузки коэффициентов: {response.status_code} — {response.text}"
        )

    return response.json()


def merge_event_odds(target_event: dict, source_event: dict):
    """
    Объединяет рынки букмекеров в одном событии.
    Нужно для ситуации, когда часть рынков грузится отдельно.
    """
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


def load_event_with_markets(sport_key: str, event: dict, regions: str, market_keys: list[str]):
    """
    Сначала пробует загрузить все рынки одним запросом.
    Если API ругается на один из рынков, пробует загрузить рынки по одному и пропустить недоступные.
    """
    event_id = event.get("id")
    warnings = []

    if not event_id:
        return None, ["У события нет ID."]

    market_string = ",".join(market_keys)

    try:
        loaded_event = fetch_event_odds(
            sport_key=sport_key,
            event_id=event_id,
            regions=regions,
            markets=market_string
        )
        return loaded_event, warnings

    except Exception as full_error:
        warnings.append(
            f"Не удалось загрузить все рынки одним запросом для матча "
            f"{event.get('home_team')} — {event.get('away_team')}. "
            f"Пробую рынки по одному."
        )

        combined_event = {
            "id": event.get("id"),
            "sport_key": event.get("sport_key"),
            "sport_title": event.get("sport_title"),
            "commence_time": event.get("commence_time"),
            "home_team": event.get("home_team"),
            "away_team": event.get("away_team"),
            "bookmakers": []
        }

        for market_key in market_keys:
            try:
                one_market_event = fetch_event_odds(
                    sport_key=sport_key,
                    event_id=event_id,
                    regions=regions,
                    markets=market_key
                )
                combined_event = merge_event_odds(combined_event, one_market_event)

            except Exception:
                warnings.append(
                    f"Рынок `{market_key}` недоступен для матча "
                    f"{event.get('home_team')} — {event.get('away_team')}."
                )

        return combined_event, warnings


def count_markets(event: dict) -> int:
    total = 0

    for bookmaker in event.get("bookmakers", []):
        total += len(bookmaker.get("markets", []))

    return total


def extract_bookmakers(events: list[dict]):
    bookmakers = set()

    for event in events:
        for bookmaker in event.get("bookmakers", []):
            title = bookmaker.get("title")
            if title:
                bookmakers.add(title)

    return sorted(bookmakers)


def build_events_text(events: list[dict], bookmaker_choice: str):
    parts = []

    for event in events:
        home_team = event.get("home_team", "Неизвестно")
        away_team = event.get("away_team", "Неизвестно")
        commence_time = event.get("commence_time", "Время не указано")

        parts.append("")
        parts.append("=" * 70)
        parts.append(f"Матч: {home_team} — {away_team}")
        parts.append(f"Время начала: {commence_time}")

        for bookmaker in event.get("bookmakers", []):
            bookmaker_title = bookmaker.get("title", "Букмекер не указан")

            if bookmaker_choice != "Все" and bookmaker_title != bookmaker_choice:
                continue

            parts.append("")
            parts.append(f"Букмекер: {bookmaker_title}")

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "unknown")
                market_name = MARKET_RU_NAMES.get(market_key, market_key)
                last_update = market.get("last_update")

                parts.append("")
                parts.append(f"Рынок: {market_name} ({market_key})")

                if last_update:
                    parts.append(f"Обновлено: {last_update}")

                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "исход")
                    price = outcome.get("price", "нет коэффициента")
                    point = outcome.get("point")
                    description = outcome.get("description")

                    line = f"- {name}"

                    if description:
                        line += f" | {description}"

                    if point is not None:
                        line += f" {point}"

                    line += f": {price}"

                    parts.append(line)

    return "\n".join(parts)


def make_preview_table(events: list[dict]):
    rows = []

    for event in events:
        rows.append({
            "Матч": f"{event.get('home_team')} — {event.get('away_team')}",
            "Начало": event.get("commence_time"),
            "Букмекеров": len(event.get("bookmakers", [])),
            "Рынков": count_markets(event)
        })

    return pd.DataFrame(rows)


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


# ============================================================
# OPENAI АНАЛИЗ
# ============================================================

def analyze_with_openai(
    bankroll: float,
    risk_mode: str,
    sport_title: str,
    bookmaker_choice: str,
    odds_text: str,
    selected_market_keys: list[str]
):
    bankroll_plan = get_bankroll_plan(bankroll, risk_mode)

    # Чтобы запрос не был слишком огромным
    odds_text = odds_text[:18000]

    prompt = f"""
Ты спортивный аналитик для веб-приложения по анализу ставок.

ТВОЯ ЗАДАЧА:
Проанализировать только те матчи, рынки и коэффициенты, которые переданы ниже.
Нужно предложить ставки с контролем риска по банку пользователя.

ВАЖНЫЕ ПРАВИЛА:
1. Используй только переданные матчи.
2. Используй только переданные рынки.
3. Используй только переданные коэффициенты.
4. Не придумывай матчи.
5. Не придумывай коэффициенты.
6. Не добавляй рынки, которых нет во входных данных.
7. Не обещай гарантированную прибыль.
8. Основной упор делай на ординары.
9. Экспресс предлагай только если есть 2–3 логичных события.
10. Минимальный желательный коэффициент — от 1.45.
11. Не советуй ставить весь банк.
12. Не превышай общий риск на день.
13. Если данных мало, честно напиши, что ставка рискованная.

ОСОБО ВАЖНО:
- Можно анализировать не только исходы, форы и тоталы.
- Обязательно рассматривай ОБЗ, двойной шанс, исход без ничьей, индивидуальные тоталы команд, угловые, карточки и другие рынки, если они есть во входных данных.
- Комбо "исход + тотал" можно предложить только как осторожный вариант, если в данных есть оба отдельных рынка. Если готового коэффициента на комбо нет, не выдавай его как точный букмекерский коэффициент.
- Ставки на угловые и карточки анализируй отдельно от ставок на голы.
- Если рынок по ударам, ударам в створ, аутам или фолам отсутствует во входных данных, прямо напиши, что линия по этому показателю не была найдена.

ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
Банк: {bankroll}
Режим риска: {risk_mode}
Спорт: {sport_title}
Букмекер: {bookmaker_choice}
Выбранные рынки: {", ".join(selected_market_keys)}

ЛИМИТЫ ПО БАНКУ:
Лимит риска на день: {bankroll_plan["daily_limit"]}
Низкая ставка: {bankroll_plan["single_low"]}
Средняя ставка: {bankroll_plan["single_medium"]}
Высокая ставка: {bankroll_plan["single_high"]}
Экспресс: {bankroll_plan["express"]}

ДАННЫЕ КОЭФФИЦИЕНТОВ:
{odds_text}

Ответ дай строго на русском языке.

Структура ответа:

# Краткая оценка линии

Оцени, насколько линия подходит для ставок.

# Лучшие ординары

Дай 2–5 вариантов.
Для каждого варианта укажи:

- Матч:
- Рынок:
- Коэффициент:
- Сумма ставки:
- Риск:
- Уверенность от 1 до 10:
- Объяснение:

# Ставки на голы

Отдельно оцени:
- тоталы;
- индивидуальные тоталы;
- ОБЗ.

# Исходы и защита от ничьей

Отдельно оцени:
- победа;
- двойной шанс;
- исход без ничьей;
- исход с учётом форы.

# Статистика команд

Отдельно оцени, если есть в линии:
- угловые;
- карточки;
- удары;
- удары в створ;
- ауты;
- фолы.

Если какого-то показателя нет во входных данных, прямо напиши: "линия не найдена".

# Комбо: исход + тотал

Предложи только если это логично.
Если нет готового коэффициента, напиши, что это не точная линия букмекера, а ориентир.

# Экспресс

Напиши:
- стоит ли собирать экспресс;
- события;
- общий коэффициент;
- сумма;
- риск;
- объяснение.

# Что лучше пропустить

Перечисли рискованные матчи или рынки.

# Общий риск на день

Посчитай примерную сумму всех ставок и процент от банка.

# Итог

Дай короткий вывод: как лучше сыграть сегодня.

# Предупреждение

Кратко напомни, что ставки несут риск и не гарантируют прибыль.
"""

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            reasoning={"effort": "low"},
            input=prompt
        )

        return response.output_text

    except Exception as e:
        return f"""
# Ошибка при обращении к OpenAI

Техническая ошибка:

`{e}`

Что сделать:

1. Нажми кнопку анализа ещё раз через 1–2 минуты.
2. Уменьши количество матчей до 2–3.
3. Уменьши количество выбранных рынков.
4. Проверь, что в Streamlit Secrets правильно добавлен `OPENAI_API_KEY`.
5. Проверь, что в OpenAI Platform есть активный биллинг.
"""


# ============================================================
# БОКОВАЯ ПАНЕЛЬ
# ============================================================

st.sidebar.header("⚙️ Настройки анализа")

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
    max_value=10,
    value=3
)

st.sidebar.divider()

st.sidebar.subheader("🎯 Рынки для поиска")

selected_market_labels = st.sidebar.multiselect(
    "Выбери рынки",
    list(MARKET_LABELS.keys()),
    default=DEFAULT_MARKETS
)

custom_markets_input = st.sidebar.text_area(
    "Дополнительные market keys вручную",
    placeholder="Например: totals_fouls,spreads_throw_ins",
    help=(
        "Используй это поле, если знаешь точные market keys из своего odds API. "
        "Если ключ не поддерживается The Odds API, приложение просто пропустит этот рынок."
    )
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

# Убираем дубликаты
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
selected_sport_title = selected_sport_label.split(" — ")[0]


if "loaded_events" not in st.session_state:
    st.session_state.loaded_events = []

if "load_warnings" not in st.session_state:
    st.session_state.load_warnings = []


st.subheader("2. Загрузи события и коэффициенты")

st.info(
    "Дополнительные рынки могут расходовать больше лимита The Odds API, "
    "потому что приложение загружает коэффициенты отдельно по каждому матчу."
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

                if loaded_event:
                    loaded_events.append(loaded_event)

                load_warnings.extend(warnings)

                progress.progress((index + 1) / max(len(base_events), 1))

            st.session_state.loaded_events = loaded_events
            st.session_state.load_warnings = load_warnings

            if not loaded_events:
                st.warning("События не найдены. Попробуй другой спорт, регион или рынки.")
            else:
                st.success(f"Загружено событий: {len(loaded_events)}")

        except Exception as e:
            st.error(str(e))


events = st.session_state.loaded_events
load_warnings = st.session_state.load_warnings


if load_warnings:
    with st.expander("Предупреждения по загрузке рынков"):
        for warning in load_warnings[:50]:
            st.write(f"- {warning}")


if events:
    st.subheader("3. Выбери букмекера")

    bookmakers = extract_bookmakers(events)

    if not bookmakers:
        st.warning(
            "Букмекеры или рынки не найдены. "
            "Попробуй выбрать меньше рынков или другой регион."
        )
        st.stop()

    bookmaker_choice = st.selectbox(
        "Букмекер",
        ["Все"] + bookmakers
    )

    st.subheader("4. Найденные события")

    preview_df = make_preview_table(events)

    st.dataframe(
        preview_df,
        use_container_width=True
    )

    odds_text = build_events_text(
        events=events,
        bookmaker_choice=bookmaker_choice
    )

    with st.expander("Показать коэффициенты, которые будут отправлены на анализ"):
        st.text(odds_text)

    st.subheader("5. Запусти AI-анализ")

    st.write(
        "Для стабильной работы лучше начинать с 2–3 матчей и 5–8 рынков. "
        "Если всё работает, можно увеличивать количество."
    )

    if st.button("🧠 Проанализировать и предложить ставки"):
        if not odds_text.strip():
            st.warning("Нет данных для анализа. Попробуй выбрать другого букмекера или меньше рынков.")
        else:
            with st.spinner("Анализирую матчи, коэффициенты, статистические рынки и риск по банку..."):
                analysis = analyze_with_openai(
                    bankroll=bankroll,
                    risk_mode=risk_mode,
                    sport_title=selected_sport_title,
                    bookmaker_choice=bookmaker_choice,
                    odds_text=odds_text,
                    selected_market_keys=selected_market_keys
                )

                st.subheader("✅ Результат анализа")
                st.markdown(analysis)

else:
    st.info("Сначала выбери спорт и нажми «Загрузить коэффициенты».")


# ============================================================
# НИЖНИЙ БЛОК
# ============================================================

st.divider()

st.caption(
    "Приложение не гарантирует прибыль. Коэффициенты загружаются из внешнего odds API. "
    "Если нужного рынка или букмекера нет в API, приложение не сможет честно использовать эту линию."
)
    st.info("Сначала выбери спорт и нажми «Загрузить коэффициенты».")
