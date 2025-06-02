from pydantic import BaseModel, Field
import random
from typing import List, Dict
import logging

logger = logging.getLogger("agent_actions")

class Good(BaseModel):
    """Representation of a tradable good in the economy"""
    name: str
    quantity: int = 0
    base_price: float = 1.0

class Offer(BaseModel):
    """Representation of a trade offer"""
    seller_id: str
    good_name: str
    quantity: int
    price: float
    offer_id: str = Field(default_factory=lambda: f"offer_{random.randint(1000, 9999)}")

class Request(BaseModel):
    """Representation of a buy request"""
    buyer_id: str
    good_name: str
    quantity: int
    max_price: float
    facilitated_by_market: bool = False
    request_id: str = Field(default_factory=lambda: f"request_{random.randint(1000, 9999)}")

class Transaction(BaseModel):
    """Record of a completed transaction"""
    seller_id: str
    buyer_id: str
    good_name: str
    quantity: int
    price: float
    transaction_id: str = Field(default_factory=lambda: f"tx_{random.randint(1000, 9999)}")

class AgentState(BaseModel):
    """The state of an individual agent"""
    agent_id: str
    goods: Dict[str, int] = {}
    currency: float = 10.0
    health: int = 100
    labor_capacity: int = 5
    labor_used: int = 0
    labor_offer: float = 0.0
    transaction_history: List[str] = {}

class EconomyState(BaseModel):
    """The global state of the economy"""
    cycle: int = 0
    agents: Dict[str, AgentState] = {}
    offers: List[Offer] = []
    requests: List[Request] = []
    transactions: List[Transaction] = []
    market_prices: Dict[str, float] = {}
    cycle_logs: Dict[int, Dict[str, List[str]]] = {}
    agent_decisions: Dict[str, List[str]] = {}

    def log_agent_decision(self, agent_id: str, decision: str) -> None:
        """Log a decision made by an agent in the current cycle"""
        if agent_id not in self.agent_decisions:
            self.agent_decisions[agent_id] = []
        message = f"[Cycle {self.cycle}] {agent_id}: {decision}"
        self.agent_decisions[agent_id].append(message)
        logger.info(message)  # Log to the main logger immediately
        
    def finalize_cycle_logs(self) -> None:
        """Move current cycle decisions to permanent logs"""
        if self.agent_decisions:
            self.cycle_logs[self.cycle] = self.agent_decisions.copy()
            self.agent_decisions.clear()  # Clear for next cycle

    def get_agent_cycle_log(self, agent_id: str, cycle: int) -> list:
        return self.cycle_logs.get(cycle, {}).get(agent_id, [])

    def save_logs_to_file(self, filename: str = "agent_decisions.log") -> None:
        """Save all agent decisions to a log file"""
        with open(filename, "w") as f:
            f.write("=== MICRO TRADE ECONOMY SIMULATION LOGS ===\n\n")
            for cycle, agents_data in sorted(self.cycle_logs.items()):
                f.write(f"CYCLE {cycle}\n")
                f.write("=" * 50 + "\n")
                for agent_id, decisions in sorted(agents_data.items()):
                    f.write(f"\n{agent_id.upper()} DECISIONS:\n")
                    f.write("-" * 30 + "\n")
                    for decision in decisions:
                        f.write(f"  • {decision}\n")
                f.write("\n" + "=" * 50 + "\n\n")

    def get_agent_state(self, agent_id: str):
        return self.agents.get(agent_id)

    def add_agent(self, agent_id: str) -> None:
        if agent_id not in self.agents:
            self.agents[agent_id] = AgentState(agent_id=agent_id)

    def update_market_price(self, good_name: str, price: float) -> None:
        self.market_prices[good_name] = price

    def mark_failed_food_cycle(self, agent_id: str):
        agent = self.get_agent_state(agent_id)
        if agent:
            if not hasattr(agent, 'failed_food_cycles'):
                agent.failed_food_cycles = 1
            else:
                agent.failed_food_cycles += 1
            self.log_agent_decision(agent_id, f"Failed to buy food. Failed cycles: {agent.failed_food_cycles}")

    def cancel_request(self, request_id: str) -> bool:
        request = next((r for r in self.requests if r.request_id == request_id), None)
        if request:
            buyer_state = self.get_agent_state(request.buyer_id)
            if buyer_state:
                refund_amount = request.max_price * request.quantity
                buyer_state.currency += refund_amount
                self.log_agent_decision(request.buyer_id, f"Request {request_id} cancelled. Refunded {refund_amount:.2f}.")
                self.mark_failed_food_cycle(request.buyer_id)
            self.requests = [r for r in self.requests if r.request_id != request_id]
            return True
        return False

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))
        print(f"✅ Economy saved to {path}")

    @classmethod
    def load(cls, path: str) -> "EconomyState":
        with open(path, "r") as f:
            data = f.read()
        print(f"✅ Economy loaded from {path}")
        return cls.parse_raw(data)

class Economy:
    def __init__(self):
        # More balanced initial currency distribution
        self.producer = AgentState('producer', currency=10.0, goods={'food': 4})
        self.consumer = AgentState('consumer', currency=8.0)
        self.worker = AgentState('worker', currency=8.0)
        self.trader = AgentState('trader', currency=8.0)
        self.market = AgentState('market', currency=6.0, goods={'food': 2})
        
        # Lower initial market price to kickstart trading
        self.market_prices = {'food': 1.0}
        
        # Labor market settings
        self.base_labor_cost = 0.8
        self.min_labor_cost = 0.6
        self.max_labor_cost = 1.2
