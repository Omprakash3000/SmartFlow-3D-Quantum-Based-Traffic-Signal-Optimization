from typing import Dict, List, Optional
from backend.app.models.simulation_models import (
    ApproachDirection,
    LaneState,
    ApproachState,
    IntersectionState,
    SignalColor,
)
from backend.app.simulation.traffic_light import TrafficLightController


class Lane:
    def __init__(
        self,
        lane_id: str,
        approach: ApproachDirection,
        length_m: float = 140.0,
        speed_limit_mps: float = 13.89,
    ):
        self.lane_id = lane_id
        self.approach = approach
        self.length_m = length_m
        self.speed_limit_mps = speed_limit_mps


class Approach:
    def __init__(
        self,
        approach: ApproachDirection,
        num_lanes: int = 2,
        length_m: float = 140.0,
        speed_limit_mps: float = 13.89,
    ):
        self.approach = approach
        self.length_m = length_m
        self.speed_limit_mps = speed_limit_mps
        self.lanes: Dict[str, Lane] = {}
        for i in range(num_lanes):
            lane_id = f"{approach.value}_lane_{i}"
            self.lanes[lane_id] = Lane(
                lane_id=lane_id,
                approach=approach,
                length_m=length_m,
                speed_limit_mps=speed_limit_mps,
            )


class Intersection:
    def __init__(
        self,
        intersection_id: str,
        name: str,
        x: float,
        y: float,
        offset_s: float = 0.0,
    ):
        self.intersection_id = intersection_id
        self.name = name
        self.x = x
        self.y = y
        self.approaches: Dict[ApproachDirection, Approach] = {
            ApproachDirection.NORTHBOUND: Approach(ApproachDirection.NORTHBOUND, num_lanes=2),
            ApproachDirection.SOUTHBOUND: Approach(ApproachDirection.SOUTHBOUND, num_lanes=2),
            ApproachDirection.EASTBOUND: Approach(ApproachDirection.EASTBOUND, num_lanes=2),
            ApproachDirection.WESTBOUND: Approach(ApproachDirection.WESTBOUND, num_lanes=2),
        }
        self.traffic_light = TrafficLightController(
            intersection_id=intersection_id,
            offset_s=offset_s,
        )


class RoadNetwork:
    """
    Road network containing one or more intersections and arterial connections.
    """

    def __init__(self, topology: str = "two_corridor", speed_limit_mps: float = 13.89):
        self.topology = topology
        self.speed_limit_mps = speed_limit_mps
        self.intersections: Dict[str, Intersection] = {}
        self.downstream_connections: Dict[str, Dict[str, str]] = {}
        self._build_network()

    def _build_network(self) -> None:
        if self.topology == "single_intersection":
            self.intersections["INT_1"] = Intersection(
                intersection_id="INT_1",
                name="Central Junction",
                x=0.0,
                y=0.0,
            )
        elif self.topology == "two_corridor":
            # 2 coordinated intersections separated by 240m on the East-West arterial
            self.intersections["INT_1"] = Intersection(
                intersection_id="INT_1",
                name="West Crossing",
                x=-100.0,
                y=0.0,
                offset_s=0.0,
            )
            self.intersections["INT_2"] = Intersection(
                intersection_id="INT_2",
                name="East Crossing",
                x=100.0,
                y=0.0,
                offset_s=15.0,  # Coordinated offset
            )
            # Connecting link: EB outflow of INT_1 connects to EB inflow of INT_2
            self.downstream_connections["INT_1"] = {
                ApproachDirection.EASTBOUND.value: "INT_2"
            }
            self.downstream_connections["INT_2"] = {
                ApproachDirection.WESTBOUND.value: "INT_1"
            }
        elif self.topology == "grid_2x2":
            self.intersections["INT_NW"] = Intersection("INT_NW", "North-West", x=-100.0, y=100.0)
            self.intersections["INT_NE"] = Intersection("INT_NE", "North-East", x=100.0, y=100.0)
            self.intersections["INT_SW"] = Intersection("INT_SW", "South-West", x=-100.0, y=-100.0)
            self.intersections["INT_SE"] = Intersection("INT_SE", "South-East", x=100.0, y=-100.0)
        else:
            # Fallback to single intersection
            self.intersections["INT_1"] = Intersection("INT_1", "Main Junction", x=0.0, y=0.0)
