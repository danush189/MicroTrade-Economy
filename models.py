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
    min_food_price: float = 1.0
    max_food_price: float = 2.5
    tax_rate: float = 0.1
    tax_pool: float = 0.0

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

    def provide_food_subsidy(self):
        """Provide food to agents with critical health or zero inventory"""
        market_state = self.get_agent_state("market")
        for agent_id, agent_state in self.agents.items():
            if agent_id != "market" and (agent_state.health < 50 or agent_state.goods.get("food", 0) == 0):
                if market_state.goods.get("food", 0) > 0:
                    market_state.goods["food"] -= 1
                    agent_state.goods["food"] = agent_state.goods.get("food", 0) + 1
                    self.log_agent_decision(agent_id, "Received emergency food subsidy")

    def redistribute_tax_pool(self):
        """Redistribute wealth to prevent poverty traps"""
        total_currency = sum(agent.currency for agent in self.agents.values())
        self.tax_pool = total_currency * self.tax_rate
        
        # Identify agents in need (low health or low currency)
        agents_in_need = [
            agent_id for agent_id, agent in self.agents.items()
            if agent.health < 70 or agent.currency < self.market_prices.get("food", 1.0) * 2
        ]
        
        if agents_in_need:
            subsidy_per_agent = self.tax_pool / len(agents_in_need)
            for agent_id in agents_in_need:
                self.agents[agent_id].currency += subsidy_per_agent
                self.log_agent_decision(agent_id, f"Received {subsidy_per_agent:.2f} currency subsidy")

    def update_market_price(self, good_name: str, price: float) -> None:
        """Update market price with price controls"""
        if good_name == "food":
            # Ensure price stays within bounds
            self.market_prices[good_name] = max(self.min_food_price, min(self.max_food_price, price))
        else:
            self.market_prices[good_name] = price

    def natural_health_recovery(self):
        """Implement gradual health recovery for all agents"""
        for agent_id, agent in self.agents.items():
            if agent.health < 100:
                recovery = 2  # Small natural recovery
                agent.health = min(100, agent.health + recovery)
                if recovery > 0:
                    self.log_agent_decision(agent_id, f"Natural health recovery: +{recovery} (Current: {agent.health})")

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
    def __init__(self):        # More balanced initial currency distribution
        self.producer = AgentState('producer', currency=10.0, goods={'food': 4})
        self.worker = AgentState('worker', currency=8.0)
        self.trader = AgentState('trader', currency=8.0)
        self.market = AgentState('market', currency=6.0, goods={'food': 2})
        
        # Lower initial market price to kickstart trading
        self.market_prices = {'food': 1.0}
        
        # Labor market settings
        self.base_labor_cost = 0.8
        self.min_labor_cost = 0.6
        self.max_labor_cost = 1.2

    def provide_subsidies(self):
        for agent in self.agents:
            if agent.currency < 5:
                subsidy = 2.0
                agent.currency += subsidy
                self.log(f"{agent.name}: Received {subsidy} currency subsidy")

    def boost_food_production(self):
        """Increase food production by providing incentives to producers."""
        producer_state = self.get_agent_state("producer")
        if producer_state:
            producer_state.goods["food"] += 2  # Boost food production
            producer_state.currency -= 1  # Cost of production boost
            self.log_agent_decision("producer", "Boosted food production by 2 units")

    def provide_health_subsidies(self):
        """Provide health subsidies to agents with low health."""
        for agent_id, agent_state in self.agents.items():
            if agent_state.health < 70:
                agent_state.health += 10  # Health subsidy
                self.log_agent_decision(agent_id, "Received health subsidy: +10 health")

    def optimize_labor_contracts(self):
        """Encourage producers to hire more labor units."""
        producer_state = self.get_agent_state("producer")
        worker_state = self.get_agent_state("worker")
        if producer_state and worker_state:
            labor_units = min(worker_state.labor_capacity, 3)  # Hire up to 3 units
            producer_state.labor_used += labor_units
            worker_state.currency += labor_units * self.base_labor_cost
            self.log_agent_decision("producer", f"Hired {labor_units} labor units")
            self.log_agent_decision("worker", f"Fulfilled labor contract for {labor_units} units")

    def enhance_market_dynamics(self):
        """Adjust market prices dynamically to incentivize trading."""
        self.update_market_price("food", self.market_prices["food"] * 0.9)  # Lower food price slightly
        self.log_agent_decision("market", "Adjusted food price to incentivize trading")

    def implement_new_policies(self):
        """Introduce policies to stabilize the economy."""
        self.provide_food_subsidy()  # Emergency food distribution
        self.redistribute_tax_pool()  # Redistribute wealth
        self.log_agent_decision("market", "Implemented new policies to stabilize the economy")

    def run_cycle(self):
        # ...existing code...
        self.provide_subsidies()
        self.boost_food_production()
        self.provide_health_subsidies()
        self.optimize_labor_contracts()
        self.enhance_market_dynamics()
        self.implement_new_policies()
        # ...existing code...
