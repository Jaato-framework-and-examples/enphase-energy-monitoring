#!/usr/bin/env python3
"""
Energy Advisor - Intelligence Layer for Home Energy Optimization

Analyzes consumption patterns and provides actionable recommendations for:
- Optimal appliance scheduling
- Solar self-consumption maximization
- Price-aware usage (Spanish PVPC tariff)
- Peak hour avoidance

Can run standalone or as a daemon providing API for automation integration.
"""

import argparse
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import sys

try:
    from influxdb_client import InfluxDBClient
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = ""
INFLUXDB_ORG = "energy_monitoring"
INFLUXDB_BUCKET = "home_energy"

# Spanish PVPC time periods (2.0 TD tariff)
PEAK_HOURS = [(10, 14), (18, 22)]  # Punta
FLAT_HOURS = [(8, 10), (14, 18), (22, 24)]  # Llana
VALLEY_HOURS = [(0, 8)]  # Valle
WEEKEND_VALLEY_ALL_DAY = True

# PVPC price estimates (€/kWh) - can be fetched from ESIOS
PRICE_ESTIMATES = {
    "peak": 0.22,
    "flat": 0.15,
    "valley": 0.08
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceEstimator:
    """Estimates electricity prices based on time periods."""
    
    @staticmethod
    def get_period(hour: int) -> str:
        """Determine if hour is peak, flat, or valley."""
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
        else:  # 22-24
            return "flat"
    
    @staticmethod
    def estimate_price(hour: int) -> float:
        """Estimate price for a given hour."""
        period = PriceEstimator.get_period(hour)
        return PRICE_ESTIMATES[period]


class PatternAnalyzer:
    """Analyzes energy consumption patterns from InfluxDB data."""
    
    def __init__(self, influxdb_url: str, token: str = ""):
        if not INFLUXDB_AVAILABLE:
            raise RuntimeError("InfluxDB client not available")
        
        self.client = InfluxDBClient(
            url=influxdb_url,
            token=token if token else None,
            org=INFLUXDB_ORG
        )
        self.bucket = INFLUXDB_BUCKET
    
    def query_consumption_by_hour(self, hours: int = 24) -> Dict[int, float]:
        """
        Query average consumption by hour of day.
        
        Args:
            hours: Number of hours to look back (default: 24 = 1 day)
        
        Returns:
            Dictionary mapping hour (0-23) to average consumption in watts
        """
        query = f'''
        SELECT MEAN("grid_consumption_w")
        FROM "{self.bucket}"
        WHERE time > now() - {hours}h
        GROUP BY time(1h)
        FILL(null)
        '''
        
        try:
            result = self.client.query_api().query(query=query)
            
            hourly_data = {i: 0.0 for i in range(24)}
            
            for table in result:
                for record in table.records:
                    hour = record.get_time().hour
                    value = float(record.get_value())
                    
                    if hour in hourly_data:
                        if hourly_data[hour] == 0.0:
                            hourly_data[hour] = value
                        else:
                            # Average multiple readings
                            hourly_data[hour] = (hourly_data[hour] + value) / 2
            
            return hourly_data
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {}
    
    def detect_peak_consumption(self, hours: int = 168) -> List[Tuple[int, float]]:
        """
        Detect consumption during peak price hours.
        
        Returns:
            List of (hour, consumption_w) tuples where hour is peak period
        """
        hourly_consumption = self.query_consumption_by_hour(hours)
        
        peak_consumption = []
        for hour, consumption in hourly_consumption.items():
            if PriceEstimator.get_period(hour) == "peak" and consumption > 0:
                peak_consumption.append((hour, consumption))
        
        return peak_consumption
    
    def get_solar_alignment_score(self, hours: int = 24) -> float:
        """
        Calculate how well consumption aligns with solar production.
        
        Returns:
            Score 0-100 (higher is better alignment)
        """
        # Simplified: Check if consumption is high during midday
        # In reality, would compare solar_production_w vs grid_consumption_w
        hourly_consumption = self.query_consumption_by_hour(hours)
        
        midday_consumption = sum(
            consumption for hour, consumption in hourly_consumption.items()
            if 12 <= hour <= 15
        )
        
        total_consumption = sum(hourly_consumption.values())
        
        if total_consumption == 0:
            return 0.0
        
        return (midday_consumption / total_consumption) * 100
    
    def get_daily_total(self) -> Dict[str, float]:
        """Get total energy consumed and exported today."""
        query = f'''
        SELECT last("grid_consumption_w"), last("grid_export_w")
        FROM "{self.bucket}"
        WHERE time > now() - 24h
        '''
        
        try:
            result = self.client.query_api().query(query=query)
            
            # Simplified - would parse properly in production
            return {"total_consumption_kwh": 15.0, "total_export_kwh": 5.0}
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {}


class RecommendationEngine:
    """Generates actionable energy optimization recommendations."""
    
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm and OLLAMA_AVAILABLE
        
        if self.use_llm:
            logger.info("Initializing Ollama client for LLM-based recommendations")
            self.llm = ollama.Client()
        self.model = "llama3.2"  # Or your preferred model
    
    def generate_rule_based_recommendations(
        self,
        peak_consumption: List[Tuple[int, float]],
        total_consumption_kwh: float,
        daily_export_kwh: float
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on rule engine.
        
        Args:
            peak_consumption: List of (hour, watts) during peak periods
            total_consumption_kwh: Total daily consumption
            daily_export_kwh: Total daily export to grid
        
        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        
        # Rule 1: Peak hour consumption
        if peak_consumption:
            total_peak_w = sum(w for _, w in peak_consumption)
            peak_ratio = total_peak_w / (total_consumption_kwh * 1000) if total_consumption_kwh > 0 else 0
            
            if peak_ratio > 0.30:  # More than 30% during peak
                savings_eur = total_peak_w * (0.22 - 0.08) / 1000  # Peak vs Valley price diff
                savings_year = savings_eur * 365
                
                recommendations.append({
                    "type": "peak_hour_shift",
                    "severity": "high" if peak_ratio > 0.50 else "medium",
                    "title": f"Shift {peak_ratio:.0%} of consumption to off-peak hours",
                    "description": (
                        f"You consume {peak_ratio:.1%} of energy during peak hours "
                        f"(10:00-14:00, 18:00-22:00) when prices are highest. "
                        f"Shifting flexible loads to valley hours (23:00-08:00) could save "
                        f"~€{savings_year:.0f}/year."
                    ),
                    "actions": [
                        f"Schedule dishwasher to run at 23:00 instead of after dinner",
                        f"Run washing machine and dryer on weekends or after 22:00",
                        f"Charge EV during valley hours (23:00-07:00)"
                    ],
                    "estimated_savings_eur_per_year": savings_year
                })
        
        # Rule 2: Poor solar alignment
        # This would use get_solar_alignment_score() in full implementation
        if daily_export_kwh < total_consumption_kwh * 0.2:  # Less than 20% self-consumption
            recommendations.append({
                "type": "solar_alignment",
                "severity": "medium",
                "title": "Increase solar self-consumption",
                "description": (
                    f"Only {daily_export_kwh/total_consumption_kwh*100:.0f}% of your consumption "
                    f"is powered by your solar panels. Running appliances during midday "
                    f"(12:00-15:00) would increase your self-consumption ratio."
                ),
                "actions": [
                    "Schedule dishwasher and washing machine for 13:00-15:00",
                    "Use smart plugs to schedule appliances during solar peak hours"
                ],
                "estimated_savings_eur_per_year": 150.0  # Placeholder
            })
        
        return recommendations
    
    def generate_llm_recommendations(
        self,
        consumption_data: Dict[str, Any],
        context: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations using LLM for deeper insights.
        
        Args:
            consumption_data: Dictionary with consumption metrics
            context: Additional context string
        
        Returns:
            List of recommendation dictionaries
        """
        if not self.use_llm:
            return []
        
        try:
            # Build prompt for LLM
            prompt = f"""You are an expert home energy advisor. Analyze this data and provide actionable recommendations.

Current consumption patterns:
{json.dumps(consumption_data, indent=2)}

Context: {context}

Provide 2-3 specific recommendations in JSON format:
[
  {{
    "type": "recommendation_type",
    "severity": "high|medium|low",
    "title": "Brief title",
    "description": "Detailed explanation",
    "actions": ["action1", "action2"],
    "estimated_savings_eur_per_year": 0.0
  }}
]

Only respond with valid JSON. No markdown, no explanations outside JSON.
"""
            
            response = self.llm.generate(
                model=self.model,
                prompt=prompt
            )
            
            # Parse LLM response
            # In production, would validate JSON schema
            raw_response = response['response']
            
            # Try to extract JSON from response
            start_idx = raw_response.find('[')
            end_idx = raw_response.rfind(']')
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = raw_response[start_idx+1:end_idx]
                recommendations = json.loads(json_str)
                return recommendations
            else:
                logger.warning("Could not extract JSON from LLM response")
                return []
            
        except Exception as e:
            logger.error(f"LLM recommendation failed: {e}")
            return []


class EnergyAdvisordaemon:
    """Main orchestrator for energy intelligence layer."""
    
    def __init__(
        self,
        influxdb_url: str = INFLUXDB_URL,
        use_llm: bool = True
    ):
        self.influxdb_url = influxdb_url
        self.use_llm = use_llm
        
        # Initialize components
        self.analyzer = PatternAnalyzer(influxdb_url)
        self.recommender = RecommendationEngine(use_llm=use_llm)
    
    def analyze_and_recommend(self) -> Dict[str, Any]:
        """
        Perform complete analysis and generate recommendations.
        
        Returns:
            Dictionary with analysis and recommendations
        """
        logger.info("Starting energy pattern analysis...")
        
        # Collect data
        peak_consumption = self.analyzer.detect_peak_consumption()
        daily_totals = self.analyzer.get_daily_total()
        solar_score = self.analyzer.get_solar_alignment_score()
        
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "daily_consumption_kwh": daily_totals.get("total_consumption_kwh", 0),
            "daily_export_kwh": daily_totals.get("total_export_kwh", 0),
            "solar_alignment_score": solar_score,
            "peak_hour_consumption": [
                {"hour": h, "watts": w} for h, w in peak_consumption
            ]
        }
        
        # Generate recommendations
        logger.info("Generating recommendations...")
        
        # Rule-based (always available)
        rule_recommendations = self.recommender.generate_rule_based_recommendations(
            peak_consumption=peak_consumption,
            total_consumption_kwh=analysis["daily_consumption_kwh"],
            daily_export_kwh=analysis["daily_export_kwh"]
        )
        
        # LLM-based (if enabled)
        llm_recommendations = []
        if self.use_llm:
            logger.info("Generating LLM-based recommendations...")
            llm_recommendations = self.recommender.generate_llm_recommendations(
                consumption_data=analysis,
                context="User is in Spain with PVPC tariff and has solar panels"
            )
        
        return {
            "analysis": analysis,
            "recommendations": {
                "rule_based": rule_recommendations,
                "llm_enhanced": llm_recommendations
            }
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Energy Advisor - Home Energy Optimization Intelligence",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--influxdb-url',
        default=INFLUXDB_URL,
        help='InfluxDB URL'
    )
    
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Disable LLM-based recommendations (rules only)'
    )
    
    parser.add_argument(
        '--analyze-once',
        action='store_true',
        help='Run analysis once and exit'
    )
    
    parser.add_argument(
        '--output',
        choices=['json', 'pretty'],
        default='pretty',
        help='Output format'
    )
    
    args = parser.parse_args()
    
    # Create advisor
    try:
        advisor = EnergyAdvisordaemon(
            influxdb_url=args.influxdb_url,
            use_llm=not args.no_llm
        )
    except RuntimeError as e:
        logger.error(f"Failed to initialize advisor: {e}")
        logger.error("Make sure InfluxDB is running and accessible")
        sys.exit(1)
    
    # Run analysis
    result = advisor.analyze_and_recommend()
    
    # Output
    if args.output == 'json':
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "="*60)
        print("  ENERGY ADVISOR REPORT")
        print("="*60 + "\n")
        
        analysis = result['analysis']
        print(f"📊 Analysis Summary")
        print(f"  Daily consumption: {analysis['daily_consumption_kwh']:.1f} kWh")
        print(f"  Daily export: {analysis['daily_export_kwh']:.1f} kWh")
        print(f"  Solar alignment score: {analysis['solar_alignment_score']:.0f}/100")
        print()
        
        recs = result['recommendations']
        
        if recs['rule_based']:
            print(f"💡 Rule-Based Recommendations ({len(recs['rule_based'])})")
            for i, rec in enumerate(recs['rule_based'], 1):
                print(f"\n{i}. {rec['title']}")
                print(f"   {rec['description']}")
                print("   Actions:")
                for action in rec['actions']:
                    print(f"     • {action}")
                if rec.get('estimated_savings_eur_per_year'):
                    print(f"   💰 Estimated savings: €{rec['estimated_savings_eur_per_year']:.0f}/year")
        
        if recs['llm_enhanced']:
            print(f"\n\n🤖 AI-Enhanced Recommendations ({len(recs['llm_enhanced'])})")
            for i, rec in enumerate(recs['llm_enhanced'], 1):
                print(f"\n{i}. {rec['title']}")
                print(f"   {rec['description']}")
                if rec.get('actions'):
                    print("   Actions:")
                    for action in rec['actions']:
                        print(f"     • {action}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
