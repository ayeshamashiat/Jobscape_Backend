"""
Commute score calculation routes
Calculates distance and travel time between user location and job location
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import math
import requests
import os

router = APIRouter(prefix="/commute", tags=["commute"])


class CommuteScoreRequest(BaseModel):
    """Request model for commute score calculation"""
    origin_lat: float = Field(..., ge=-90, le=90, description="Origin latitude")
    origin_lng: float = Field(..., ge=-180, le=180, description="Origin longitude")
    dest_lat: float = Field(..., ge=-90, le=90, description="Destination latitude")
    dest_lng: float = Field(..., ge=-180, le=180, description="Destination longitude")
    mode: Optional[str] = Field("driving", description="Travel mode: driving, transit, walking, bicycling")


class CommuteScoreResponse(BaseModel):
    """Response model for commute score"""
    score: int = Field(..., ge=0, le=100, description="Commute score (0-100, higher is better)")
    rating: str = Field(..., description="Rating: Excellent, Good, Moderate, Long, Very Long")
    distance_km: float = Field(..., description="Straight-line distance in km")
    travel_distance_km: float = Field(..., description="Actual travel distance in km")
    duration_minutes: Optional[float] = Field(None, description="Estimated travel duration in minutes")
    straight_line_distance: float = Field(..., description="Direct distance (same as distance_km)")
    mode: str = Field(..., description="Travel mode used")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on earth
    Uses Haversine formula
    
    Args:
        lat1, lon1: First point coordinates (decimal degrees)
        lat2, lon2: Second point coordinates (decimal degrees)
    
    Returns:
        Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in kilometers
    radius_km = 6371
    
    return c * radius_km


def calculate_commute_score(distance_km: float, duration_minutes: Optional[float] = None) -> int:
    """
    Calculate commute score from 0-100 based on distance and duration
    
    Score breakdown:
    - 100: <= 5 km (excellent, very close)
    - 90: <= 10 km (excellent)
    - 75: <= 20 km (good)
    - 60: <= 30 km (moderate)
    - 40: <= 50 km (long)
    - 20: <= 75 km (very long)
    - 10: > 75 km (extremely long)
    
    Duration can further reduce score if travel time is excessive
    
    Args:
        distance_km: Distance in kilometers
        duration_minutes: Optional travel duration in minutes
    
    Returns:
        Score from 0 to 100
    """
    # Base score on distance
    if distance_km <= 5:
        base_score = 100
    elif distance_km <= 10:
        base_score = 90
    elif distance_km <= 20:
        base_score = 75
    elif distance_km <= 30:
        base_score = 60
    elif distance_km <= 50:
        base_score = 40
    elif distance_km <= 75:
        base_score = 20
    else:
        base_score = 10
    
    # Adjust based on duration if available
    if duration_minutes:
        if duration_minutes <= 15:
            time_multiplier = 1.0  # No penalty
        elif duration_minutes <= 30:
            time_multiplier = 0.95
        elif duration_minutes <= 45:
            time_multiplier = 0.85
        elif duration_minutes <= 60:
            time_multiplier = 0.75
        elif duration_minutes <= 90:
            time_multiplier = 0.6
        else:
            time_multiplier = 0.5
        
        base_score = int(base_score * time_multiplier)
    
    return max(0, min(100, base_score))


def get_rating_from_score(score: int) -> str:
    """Convert score to human-readable rating"""
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Moderate"
    elif score >= 20:
        return "Long"
    else:
        return "Very Long"


@router.post("/calculate-score", response_model=CommuteScoreResponse)
def calculate_score(request: CommuteScoreRequest):
    """
    Calculate commute score between origin and destination
    
    Returns:
    - score: 0-100 (higher is better)
    - rating: Text description
    - distance_km: Straight-line distance
    - travel_distance_km: Actual travel distance (if Google Maps API available)
    - duration_minutes: Estimated travel time (if Google Maps API available)
    
    Note: If GOOGLE_MAPS_API_KEY is not set, falls back to straight-line distance
    """
    
    # Validate travel mode
    valid_modes = ["driving", "transit", "walking", "bicycling"]
    if request.mode.lower() not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Must be one of: {', '.join(valid_modes)}"
        )
    
    # Calculate straight-line distance using Haversine formula
    distance_km = haversine_distance(
        request.origin_lat,
        request.origin_lng,
        request.dest_lat,
        request.dest_lng
    )
    
    # Try to get accurate travel time from Google Maps API if key is available
    google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    duration_minutes = None
    travel_mode_distance = distance_km
    
    if google_api_key:
        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": f"{request.origin_lat},{request.origin_lng}",
                "destinations": f"{request.dest_lat},{request.dest_lng}",
                "mode": request.mode.lower(),
                "key": google_api_key,
                "units": "metric"
            }
            
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data.get("status") == "OK" and data.get("rows"):
                element = data["rows"][0]["elements"][0]
                if element.get("status") == "OK":
                    # Distance in meters, convert to km
                    travel_mode_distance = element["distance"]["value"] / 1000
                    # Duration in seconds, convert to minutes
                    duration_minutes = element["duration"]["value"] / 60
            
        except Exception as e:
            # Fall back to haversine distance if API fails
            print(f"⚠️ Google Maps API error: {e}")
            pass
    
    # Calculate score
    score = calculate_commute_score(travel_mode_distance, duration_minutes)
    rating = get_rating_from_score(score)
    
    return CommuteScoreResponse(
        score=score,
        rating=rating,
        distance_km=round(distance_km, 2),
        travel_distance_km=round(travel_mode_distance, 2),
        duration_minutes=round(duration_minutes, 1) if duration_minutes else None,
        straight_line_distance=round(distance_km, 2),
        mode=request.mode.lower()
    )
