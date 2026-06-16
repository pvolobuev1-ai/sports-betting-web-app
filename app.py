import os
import requests
import pandas as pd
import streamlit as st
from openai import OpenAI


# =============================
# НАСТРОЙКА СТРАНИЦЫ
# =============================

st.set_page_config(
    page_title="AI Betting Analyst",
    page_icon="🏆",
    layout="wide"
)

st.title("🏆 AI Betting Analyst")
st.caption("Веб-приложение для поиска коэффициентов и анализа спортивных событий")


# =============================
# ПОЛУЧЕНИЕ СЕКРЕТНЫХ КЛЮЧЕЙ
# =============================

def get_secret(name: str) -> str:
    """
    Берёт ключ из Streamlit Secrets.
    Если приложение запущено не в Streamlit Cloud, пробует взять из переменных окружения.
    """
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name, "")


OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
ODDS_API_KEY = get_secret("ODDS_API_KEY")

if not OPENAI_API_KEY:
    st.error("Не найден OPENAI_API_KEY. Добавь ключ OpenAI в Secrets приложения.")
    st.stop()

if not ODDS_API_KEY:
    st.error("Не найден ODDS_API_KEY. Добавь ключ The Odds API в Secrets приложения.")
    st.stop()


client = OpenAI(api_key=OPENAI_API_KEY)


# =============================
# ЗАГРУЗКА ВИДОВ СПОРТА
# =============================

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


# =============================
# ЗАГРУЗКА КОЭФФИЦИЕНТОВ
# =============================

def fetch_odds(sport_key: str, regions: str, markets: str):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
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


# =============================
# ПОЛУЧЕНИЕ СПИСКА БУКМЕКЕРОВ
# =============================

def extract_bookmakers(events):
    bookmakers = set()

    for event in events:
        for bookmaker in event.get("bookmakers", []):
            title = bookmaker.get("title")
            if title:
                bookmakers.add(title)

    return sorted(bookmakers)


# =============================
# ПОДГОТОВКА ТЕКСТА ДЛЯ AI
# =============================

def build_events_text(events, bookmaker_choice: str, max_events: int):
    parts = []

    for event in events[:max_events]:
        home_team = event.get("home_team", "Неизвестно")
        away_team = event.get("away_team", "Неизвестно")
        commence_time = event.get("commence_time", "Время не указано")

        parts.append("")
        parts.append(f"Матч: {home_team} — {away_team}")
        parts.append(f"Время начала: {commence_time}")

        bookmakers = event.get("bookmakers", [])

        for bookmaker in bookmakers:
            bookmaker_title = bookmaker.get("title", "Букмекер не указан")

            if bookmaker_choice != "Все" and bookmaker_title != bookmaker_choice:
                continue

            parts.append(f"Букмекер: {bookmaker_title}")

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "unknown")

                if market_key == "h2h":
                    market_name = "Победитель матча"
                elif market_key == "spreads":
                    market_name = "Фора"
                elif market_key == "totals":
                    market_name = "Тотал"
                else:
                    market_name = market_key

                parts.append(f"Рынок: {market_name}")

                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "исход")
                    price = outcome.get("price", "нет коэффициента")
                    point = outcome.get("point")

                    if point is not None:
                        parts.append(f"- {name} {point}: {price}")
                    else:
                        parts.append(f"- {name}: {price}")

    return "\n".join(parts)


# =============================
# AI-АНАЛИЗ
# =============================

def analyze_with_openai(
    bankroll: float,
    risk_mode: str,
    sport_title: str,
    bookmaker_choice: str,
    odds_text: str
):
    prompt = f"""
Ты спортивный аналитик. Нужно проанализировать спортивные события и коэффициенты.

ВАЖНЫЕ ПРАВИЛА:
1. Анализируй только те матчи, рынки и коэффициенты, которые переданы ниже.
2. Не придумывай новые матчи.
3. Не придумывай коэффициенты.
4. Не добавляй рынки, которых нет во входных данных.
5. Не обещай гарантированную прибыль.
6. Если данных мало, честно напиши, что ставка рискованная.
7. Основной упор делай на ординары.
8. Экспресс предлагай только если есть 2–3 логичных события.
9. Минимальный желательный коэффициент — от 1.45.
10. Не советуй ставить весь банк.

БАНК ПОЛЬЗОВАТЕЛЯ: {bankroll}
РЕЖИМ РИСКА: {risk_mode}
СПОРТ: {sport_title}
БУКМЕКЕР: {bookmaker_choice}

Ограничения по риску:
- осторожный режим: до 7% банка на день;
- умеренный режим: до 10% банка на день;
- агрессивный режим: до 15% банка на день;
- одна ставка обычно не должна превышать 2–6% банка;
- экспресс — не больше 1–2% банка.

ДАННЫЕ КОЭФФИЦИЕНТОВ:
{odds_text}

Ответ дай строго на русском языке.

Структура ответа:

## Краткая оценка линии

Напиши, насколько линия подходит для ставок.

## Рекомендуемые ординары

Для каждой ставки укажи:
- матч;
- рынок;
- коэффициент;
- сумма ставки;
- риск: низкий / средний / высокий;
- уверенность от 1 до 10;
- объяснение.

## Экспресс

Напиши:
- стоит ли собирать экспресс;
- какие события включить;
- общий коэффициент;
- сумма ставки;
- риск;
- почему именно так.

## Что лучше пропустить

Перечисли рискованные матчи или рынки.

## Общий риск на день

Посчитай примерную сумму всех ставок и процент от банка.

## Предупреждение

Кратко напомни, что ставки не гарантируют прибыль.
"""

    response = client.responses.create(
        model="gpt-5.5",
        input=prompt
    )

    return response.output_text


# =============================
# БОКОВАЯ ПАНЕЛЬ
# =============================

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

markets_list = st.sidebar.multiselect(
    "Рынки",
    ["h2h", "spreads", "totals"],
    default=["h2h", "spreads", "totals"]
)

max_events = st.sidebar.slider(
    "Сколько матчей анализировать",
    min_value=1,
    max_value=20,
    value=8
)


# =============================
# ОСНОВНОЙ ИНТЕРФЕЙС
# =============================

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


if "events" not in st.session_state:
    st.session_state.events = []


st.subheader("2. Загрузи коэффициенты")

if st.button("🔎 Загрузить коэффициенты"):
    if not markets_list:
        st.warning("Выбери хотя бы один рынок.")
    else:
        try:
            markets = ",".join(markets_list)
            events = fetch_odds(selected_sport_key, regions, markets)
            st.session_state.events = events

            if len(events) == 0:
                st.warning("События не найдены. Попробуй выбрать другой спорт или регион.")
            else:
                st.success(f"Загружено событий: {len(events)}")

        except Exception as e:
            st.error(str(e))


events = st.session_state.events


if events:
    st.subheader("3. Выбери букмекера")

    bookmakers = extract_bookmakers(events)

    bookmaker_choice = st.selectbox(
        "Букмекер",
        ["Все"] + bookmakers
    )

    st.subheader("4. Найденные события")

    preview_rows = []

    for event in events[:max_events]:
        preview_rows.append({
            "Матч": f"{event.get('home_team')} — {event.get('away_team')}",
            "Начало": event.get("commence_time"),
            "Букмекеров": len(event.get("bookmakers", []))
        })

    st.dataframe(
        pd.DataFrame(preview_rows),
        use_container_width=True
    )

    odds_text = build_events_text(
        events=events,
        bookmaker_choice=bookmaker_choice,
        max_events=max_events
    )

    with st.expander("Показать коэффициенты, которые будут отправлены на анализ"):
        st.text(odds_text)

    st.subheader("5. Запусти анализ")

    if st.button("🧠 Проанализировать и предложить ставки"):
        if not odds_text.strip():
            st.warning("Нет данных для анализа. Попробуй выбрать другого букмекера.")
        else:
            with st.spinner("Анализирую матчи, коэффициенты и риск по банку..."):
                try:
                    analysis = analyze_with_openai(
                        bankroll=bankroll,
                        risk_mode=risk_mode,
                        sport_title=selected_sport_title,
                        bookmaker_choice=bookmaker_choice,
                        odds_text=odds_text
                    )

                    st.subheader("✅ Результат анализа")
                    st.markdown(analysis)

                except Exception as e:
                    st.error(f"Ошибка анализа: {e}")

else:
    st.info("Сначала выбери спорт и нажми «Загрузить коэффициенты».")
