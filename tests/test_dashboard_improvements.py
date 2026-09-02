from led_matrix_software.dashboard.state import DashboardState, TrainStatus, WeatherInfo
from led_matrix_software.dashboard.renderer import (
    build_train_text,
    build_dashboard_text,
    _short_detail,
)
from led_matrix_software.dashboard.weather import (
    _parse_today_block,
    _parse_current_humidity,
)
from bs4 import BeautifulSoup


def test_temperature_parsing_excludes_tempdiff():
    # Simulated HTML matching tenki.jp structure
    html = """
    <section class="today-weather">
      <div class="weather-telop">晴のち曇</div>
      <dt class="high-temp sumarry">最高</dt>
      <dd class="high-temp temp">32℃</dd>
      <dd class="high-temp tempdiff">[+4]</dd>
      <dt class="low-temp sumarry">最低</dt>
      <dd class="low-temp temp">24℃</dd>
      <dd class="low-temp tempdiff">[+1]</dd>
    </section>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = _parse_today_block(soup)
    assert result["today_weather"] == "晴のち曇"
    assert result["today_high"] == "32度"
    assert result["today_low"] == "24度"


def test_humidity_parsing_matches_current_slot():
    html = """
    <table id="forecast-point-3h-today">
      <tr class="hour">
        <td>03</td><td>06</td><td>09</td><td>12</td><td>15</td><td>18</td><td>21</td><td>24</td>
      </tr>
      <tr class="humidity">
        <td>94</td><td>96</td><td>79</td><td>68</td><td>65</td><td>70</td><td>81</td><td>87</td>
      </tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    hum = _parse_current_humidity(soup)
    assert hum.endswith("%")
    val = int(hum.removesuffix("%"))
    assert 60 <= val <= 100


def test_train_text_normal_when_no_abnormalities():
    state = DashboardState()
    state.update_trains({
        "京王本線": TrainStatus(line="京王本線", status="平常運転"),
        "京王井の頭線": TrainStatus(line="京王井の頭線", status="平常運転"),
        "東京メトロ千代田線": TrainStatus(line="東京メトロ千代田線", status="平常運転"),
        "小田急小田原線": TrainStatus(line="小田急小田原線", status="平常運転"),
    })
    # 全線正常時はコンパクトに「運行情報：平常運転」と表示
    assert build_train_text(state) == "運行情報：平常運転"
    dash = build_dashboard_text(state)
    assert "運行情報：平常運転" in dash


def test_train_text_displays_when_delayed_with_expanded_limit():
    state = DashboardState()
    long_detail = (
        "〇〇駅での人身事故の影響で、現在も一部列車に最大約30分の遅れや運休が出ています。"
        "東京メトロ各線、都営地下鉄各線、JR東日本各線への振替輸送を実施しています。"
        "ご利用のお客様には大変ご迷惑をおかけいたしますが、最新の運行情報にご注意ください。"
    )
    state.update_trains({
        "京王本線": TrainStatus(line="京王本線", status="遅延", detail=long_detail),
        "京王井の頭線": TrainStatus(line="京王井の頭線", status="平常運転"),
    })
    text = build_train_text(state)
    assert "運行情報" in text
    assert "京王本線 遅延" in text
    assert "京王井の頭線" not in text  # Normal lines omitted
    assert len(long_detail) <= 256
    assert long_detail in text  # Fully preserved up to 256 chars


def test_multi_city_weather_and_easter_egg(monkeypatch):
    state = DashboardState()
    state.update_cities_weather({
        "東京都目黒区": WeatherInfo(today_weather="晴", today_high="32度", today_low="24度"),
        "東京都府中市": WeatherInfo(today_weather="曇", today_high="31度", today_low="23度"),
        "町田市": WeatherInfo(today_weather="雨", today_high="29度", today_low="22度"),
        "埼玉県戸田市": WeatherInfo(today_weather="晴", today_high="33度", today_low="25度"),
        "神奈川県横浜市": WeatherInfo(today_weather="曇", today_high="30度", today_low="24度"),
        "千葉県君津市": WeatherInfo(today_weather="雨", today_high="28度", today_low="23度"),
    })
    state.update_trains({
        "京王本線": TrainStatus(line="京王本線", status="平常運転"),
    })

    # Test 1: Standard Tokyo Machida (< 0.05 condition not met)
    monkeypatch.setattr("random.random", lambda: 0.10)
    dash_text = build_dashboard_text(state)
    assert "目黒" in dash_text
    assert "東京都府中市" in dash_text
    assert "東京都町田市" in dash_text
    assert "埼玉県戸田市" in dash_text
    assert "神奈川県横浜市" in dash_text
    assert "千葉県君津市" in dash_text
    assert "神奈川県町田市" not in dash_text
    assert "運行情報：平常運転" in dash_text

    # Check chain order: 目黒 -> 府中市 -> 町田市 -> 戸田市 -> 横浜市 -> 君津市 -> 運行情報
    meguro_idx = dash_text.index("目黒")
    fuchu_idx = dash_text.index("東京都府中市")
    machida_idx = dash_text.index("東京都町田市")
    toda_idx = dash_text.index("埼玉県戸田市")
    yokohama_idx = dash_text.index("神奈川県横浜市")
    kimitsu_idx = dash_text.index("千葉県君津市")
    train_idx = dash_text.index("運行情報：平常運転")
    assert meguro_idx < fuchu_idx < machida_idx < toda_idx < yokohama_idx < kimitsu_idx < train_idx

    # Test 2: 5% Easter egg trigger (random < 0.05)
    monkeypatch.setattr("random.random", lambda: 0.02)
    dash_text_egg = build_dashboard_text(state)
    assert "神奈川県町田市" in dash_text_egg
    assert "東京都町田市" not in dash_text_egg
