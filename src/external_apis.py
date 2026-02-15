"""
External API integrations for Jaato Energy Advisor

Provides:
- PVPC electricity prices from ESIOS (Spanish grid)
- Weather forecasts for solar production prediction
- Tool implementations for jaato agents
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


# =============================================================================
# PVPC PRICE API (ESIOS)
# =============================================================================

class PVPCPriceFetcher:
    """
    Fetches PVPC (Precio Voluntario para el Pequeño Consumidor)
    electricity prices from ESIOS API.
    """

    ESIOS_API_URL = "https://api.esios.ree.es/indicators/1023,1024,1025"
    ESIOS_TOKEN = os.getenv("ESIOS_TOKEN", "")

    @staticmethod
    def get_prices_for_date(date: datetime) -> Dict[int, float]:
        """
        Get hourly PVPC prices for a specific date.

        Args:
            date: Date to fetch prices for

        Returns:
            Dictionary mapping hour (0-23) to price in €/kWh
        """
        try:
            # Format date for API
            date_str = date.strftime("%Y-%m-%d")

            # API request
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Host": "api.esios.ree.es"
            }

            if PVPCPriceFetcher.ESIOS_TOKEN:
                headers["Authorization"] = f"Token token={PVPCPriceFetcher.ESIOS_TOKEN}"

            # Add date range
            params = {
                "start_date": f"{date_str}T00:00:00Z",
                "end_date": f"{date_str}T23:59:59Z"
            }

            response = requests.get(
                PVPCPriceFetcher.ESIOS_API_URL,
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"ESIOS API returned {response.status_code}, using estimates")
                return PVPCPriceFetcher._get_estimated_prices()

            # Parse response
            data = response.json()

            # Extract hourly prices
            prices = {}
            for indicator in data.get("indicator", {}).get("values", []):
                # ESIOS returns timestamps - parse hour from datetime
                timestamp = indicator.get("datetime", "")
                if timestamp:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    hour = dt.hour
                    price = indicator.get("value", 0.0) / 1000  # Convert to €/kWh
                    prices[hour] = price

            if len(prices) == 24:
                logger.info(f"Retrieved {len(prices)} hourly prices from ESIOS")
                return prices
            else:
                logger.warning(f"Expected 24 prices, got {len(prices)}")
                return PVPCPriceFetcher._get_estimated_prices()

        except Exception as e:
            logger.error(f"Failed to fetch ESIOS prices: {e}")
            return PVPCPriceFetcher._get_estimated_prices()

    @staticmethod
    def _get_estimated_prices() -> Dict[int, float]:
        """
        Get estimated PVPC prices based on tariff structure.

        Returns:
            Dictionary mapping hour (0-23) to estimated price in €/kWh
        """
        # PVPC 2.0 TD tariff estimates
        prices = {}

        for hour in range(24):
            if 0 <= hour < 8:
                # Valley
                prices[hour] = 0.08
            elif 8 <= hour < 10:
                # Flat
                prices[hour] = 0.15
            elif 10 <= hour < 14:
                # Peak
                prices[hour] = 0.22
            elif 14 <= hour < 18:
                # Flat
                prices[hour] = 0.15
            elif 18 <= hour < 22:
                # Peak
                prices[hour] = 0.22
            else:
                # Flat
                prices[hour] = 0.15

        return prices

    @staticmethod
    def get_price_period(hour: int) -> str:
        """Get price period for a given hour."""
        if 0 <= hour < 8:
            return "valley"
        elif 8 <= hour < 10:
            return "flat"
        elif 10 <= hour < 14:
            return "peak"
        elif 14 <= hour < 18:
            return "flat"
        elif 18 <= hour < 22:
            return "peak"
        else:
            return "flat"


# =============================================================================
# WEATHER FORECAST API
# =============================================================================

class WeatherForecastFetcher:
    """
    Fetches weather forecasts for solar production prediction.
    Uses OpenWeatherMap API (free tier available).
    """

    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    OPENWEATHER_API_URL = "https://api.openweathermap.org/data/2.5/forecast"

    def __init__(self, latitude: float = 40.4168, longitude: float = -3.7038):
        """
        Initialize weather fetcher.

        Args:
            latitude: Location latitude (default: Madrid)
            longitude: Location longitude (default: Madrid)
        """
        self.latitude = latitude
        self.longitude = longitude

    def get_forecast(self, hours: int = 24) -> List[Dict]:
        """
        Get weather forecast for next N hours.

        Args:
            hours: Number of hours to forecast

        Returns:
            List of hourly forecast data
        """
        if not WeatherForecastFetcher.OPENWEATHER_API_KEY:
            logger.warning("OpenWeatherMap API key not set, using estimates")
            return self._get_estimated_forecast(hours)

        try:
            params = {
                "lat": self.latitude,
                "lon": self.longitude,
                "appid": WeatherForecastFetcher.OPENWEATHER_API_KEY,
                "units": "metric",
                "cnt": hours // 3  # API returns 3-hour intervals
            }

            response = requests.get(
                WeatherForecastFetcher.OPENWEATHER_API_URL,
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"Weather API returned {response.status_code}")
                return self._get_estimated_forecast(hours)

            data = response.json()

            # Parse forecast
            forecasts = []
            for item in data.get("list", []):
                dt = datetime.fromisoformat(item.get("dt_txt", ""))
                clouds = item.get("clouds", {}).get("all", 0)
                weather_main = item.get("weather", [{}])[0].get("main", "Clear")

                forecasts.append({
                    "datetime": dt,
                    "hour": dt.hour,
                    "cloud_coverage_pct": clouds,
                    "weather_condition": weather_main,
                    "solar_potential": self._calculate_solar_potential(clouds, weather_main, dt.hour)
                })

            logger.info(f"Retrieved {len(forecasts)} weather forecasts")
            return forecasts

        except Exception as e:
            logger.error(f"Failed to fetch weather forecast: {e}")
            return self._get_estimated_forecast(hours)

    def _calculate_solar_potential(self, clouds: int, condition: str, hour: int) -> float:
        """
        Calculate solar production potential (0-1 scale).

        Args:
            clouds: Cloud coverage percentage
            condition: Weather condition (Clear, Clouds, Rain, etc.)
            hour: Hour of day

        Returns:
            Solar potential score (0-1)
        """
        # Base potential from sun position
        if 6 <= hour <= 8:
            sun_potential = 0.3
        elif 9 <= hour <= 11:
            sun_potential = 0.7
        elif 12 <= hour <= 15:
            sun_potential = 1.0
        elif 16 <= hour <= 18:
            sun_potential = 0.6
        elif 19 <= hour <= 21:
            sun_potential = 0.2
        else:
            sun_potential = 0.0

        # Adjust for clouds
        cloud_factor = (100 - clouds) / 100

        # Adjust for weather condition
        condition_factor = 1.0
        if condition in ["Rain", "Drizzle", "Thunderstorm"]:
            condition_factor = 0.3
        elif condition in ["Clouds", "Mist", "Fog"]:
            condition_factor = 0.6

        return sun_potential * cloud_factor * condition_factor

    def _get_estimated_forecast(self, hours: int) -> List[Dict]:
        """Generate estimated forecast based on typical patterns."""
        forecasts = []
        now = datetime.now()

        for i in range(hours):
            dt = now + timedelta(hours=i)
            hour = dt.hour

            # Typical pattern for Spain
            if 6 <= hour <= 8:
                clouds = 30
                condition = "Clear"
            elif 9 <= hour <= 15:
                clouds = 20
                condition = "Clear"
            elif 16 <= hour <= 18:
                clouds = 40
                condition = "Clouds"
            elif 19 <= hour <= 21:
                clouds = 60
                condition = "Clouds"
            else:
                clouds = 50
                condition = "Clouds"

            forecasts.append({
                "datetime": dt,
                "hour": hour,
                "cloud_coverage_pct": clouds,
                "weather_condition": condition,
                "solar_potential": self._calculate_solar_potential(clouds, condition, hour)
            })

        return forecasts


# =============================================================================
# TOOL IMPLEMENTATIONS FOR JAATO AGENTS
# =============================================================================

def fetch_pvpc_prices(date: Optional[datetime] = None) -> Dict[int, float]:
    """
    Tool: Fetch PVPC prices from ESIOS API.

    Args:
        date: Date to fetch prices for (default: today)

    Returns:
        Dictionary mapping hour to price in €/kWh
    """
    if date is None:
        date = datetime.now()

    fetcher = PVPCPriceFetcher()
    return fetcher.get_prices_for_date(date)


def fetch_weather_forecast(
    hours: int = 24,
    latitude: float = 40.4168,
    longitude: float = -3.7038
) -> List[Dict]:
    """
    Tool: Fetch weather forecast for solar prediction.

    Args:
        hours: Number of hours to forecast
        latitude: Location latitude
        longitude: Location longitude

    Returns:
        List of hourly forecasts
    """
    fetcher = WeatherForecastFetcher(latitude, longitude)
    return fetcher.get_forecast(hours)


def calculate_savings(
    current_consumption_kwh: float,
    peak_ratio: float,
    current_price: float,
    valley_price: float = 0.08
) -> Dict[str, float]:
    """
    Tool: Calculate savings from load shifting.

    Args:
        current_consumption_kwh: Daily consumption
        peak_ratio: Fraction of consumption during peak hours
        current_price: Current electricity price
        valley_price: Valley price (default: 0.08)

    Returns:
        Dictionary with savings calculations
    """
    peak_consumption = current_consumption_kwh * peak_ratio
    price_diff = current_price - valley_price

    daily_savings = peak_consumption * price_diff
    annual_savings = daily_savings * 365

    return {
        "daily_savings_eur": round(daily_savings, 2),
        "annual_savings_eur": round(annual_savings, 0),
        "peak_consumption_kwh": round(peak_consumption, 2),
        "price_diff_eur_kwh": round(price_diff, 3)
    }


def calculate_self_consumption(
    production_kwh: float,
    consumption_kwh: float,
    export_kwh: float
) -> Dict[str, float]:
    """
    Tool: Calculate self-consumption metrics.

    Args:
        production_kwh: Solar production
        consumption_kwh: Total consumption
        export_kwh: Energy exported to grid

    Returns:
        Dictionary with self-consumption metrics
    """
    self_consumed_kwh = production_kwh - export_kwh
    self_consumption_ratio = (self_consumed_kwh / consumption_kwh) if consumption_kwh > 0 else 0

    # Financial calculation
    export_value = export_kwh * 0.06  # Low export price
    self_consumed_value = self_consumed_kwh * 0.15  # Average retail price
    total_value = self_consumed_value + export_value

    potential_value_if_fully_self_consumed = production_kwh * 0.15
    lost_value = potential_value_if_fully_self_consumed - total_value

    return {
        "self_consumed_kwh": round(self_consumed_kwh, 2),
        "self_consumption_ratio": round(self_consumption_ratio, 3),
        "export_kwh": round(export_kwh, 2),
        "self_consumed_value_eur": round(self_consumed_value, 2),
        "export_value_eur": round(export_value, 2),
        "total_value_eur": round(total_value, 2),
        "lost_value_eur": round(lost_value, 2)
    }


# =============================================================================
# TOOL REGISTRY
# =============================================================================

JAATO_TOOLS = {
    "fetch_pvpc_prices": fetch_pvpc_prices,
    "fetch_weather_forecast": fetch_weather_forecast,
    "calculate_savings": calculate_savings,
    "calculate_self_consumption": calculate_self_consumption,
}


def get_tool(tool_name: str):
    """Get tool function by name."""
    return JAATO_TOOLS.get(tool_name)


def list_tools() -> List[str]:
    """List available tools."""
    return list(JAATO_TOOLS.keys())


if __name__ == "__main__":
    # Test: Fetch today's prices
    print("Testing PVPC Price Fetcher...")
    prices = fetch_pvpc_prices()
    print(f"Got {len(prices)} hourly prices")
    for hour in sorted(prices.keys())[:5]:
        print(f"  {hour:02d}:00 - €{prices[hour]:.3f}/kWh")

    # Test: Fetch weather forecast
    print("\nTesting Weather Forecast Fetcher...")
    forecast = fetch_weather_forecast(hours=12)
    print(f"Got {len(forecast)} forecast hours")
    for item in forecast[:3]:
        print(f"  {item['hour']:02d}:00 - {item['weather_condition']}, solar: {item['solar_potential']:.2f}")

    # Test: Calculate savings
    print("\nTesting Savings Calculator...")
    savings = calculate_savings(
        current_consumption_kwh=15.0,
        peak_ratio=0.35,
        current_price=0.22
    )
    print(f"Savings: {savings}")
