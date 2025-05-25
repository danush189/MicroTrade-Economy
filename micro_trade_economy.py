import os
import logging
import random
from typing import List, Dict, Any, Optional
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
#from langchain.tools import Tool

# Setup logger
logging.basicConfig(
    level=logging.INFO,  # Use logging.DEBUG for more detail
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()  # reads .env and sets os.environ[…]
# Verify key is loaded
assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY not found in environment!"

# Economic state models
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
    goods: Dict[str, int] = {}  # {good_name: quantity}
    currency: float = 10.0
    health: int = 100
    labor_capacity: int = 5
    labor_used: int = 0
    transaction_history: List[str] = []  # transaction IDs

class EconomyState(BaseModel):
    """The global state of the economy"""
    cycle: int = 0
    agents: Dict[str, AgentState] = {}
    offers: List[Offer] = []
    requests: List[Request] = []
    transactions: List[Transaction] = []
    market_prices: Dict[str, float] = {}  # {good_name: price}
    
    def get_agent_state(self, agent_id: str) -> AgentState:
        """Get the state of a specific agent"""
        return self.agents.get(agent_id)
    
    def add_agent(self, agent_id: str) -> None:
        """Add a new agent to the economy"""
        if agent_id not in self.agents:
            self.agents[agent_id] = AgentState(agent_id=agent_id)
    
    def update_market_price(self, good_name: str, price: float) -> None:
        """Update the market price of a good"""
        self.market_prices[good_name] = price
    def cancel_request(self, request_id: str) -> bool:
        """Cancel a request and return reserved currency"""
        request = next((r for r in self.requests if r.request_id == request_id), None)
        if request:
            # Return reserved currency to buyer
            buyer_state = self.get_agent_state(request.buyer_id)
            if buyer_state:
                refund_amount = request.max_price * request.quantity
                buyer_state.currency += refund_amount
            
            # Remove request
            self.requests = [r for r in self.requests if r.request_id != request_id]
            return True
        return False
    def save(self, path: str) -> None:
        """Save the current economy state to a JSON file."""
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))
        print(f"✅ Economy saved to {path}")

    @classmethod
    def load(cls, path: str) -> "EconomyState":
        """Load economy state from a JSON file."""
        with open(path, "r") as f:
            data = f.read()
        print(f"✅ Economy loaded from {path}")
        return cls.parse_raw(data)
# Global state to be shared by all agents
ECONOMY = EconomyState()

# Tools for agents

class ProduceTool:
    """Tool to produce goods"""
    
    def __init__(self, good_name: str, production_rate: int = 1):
        self.good_name = good_name
        self.production_rate = production_rate
    
    def run(self, agent_id: str) -> str:
        """Produce goods and add them to agent's inventory"""
        agent_state = ECONOMY.get_agent_state(agent_id)
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        
        # Add produced goods to inventory
        if self.good_name not in agent_state.goods:
            agent_state.goods[self.good_name] = 0
        
        agent_state.goods[self.good_name] += self.production_rate
        
        return f"Produced {self.production_rate} units of {self.good_name}. You now have {agent_state.goods[self.good_name]} units."

class ConsumeTool:
    """Tool to consume goods"""
    
    def run(self, agent_id: str, good_name: str, quantity: int = 1) -> str:
        """Consume goods from agent's inventory"""
        agent_state = ECONOMY.get_agent_state(agent_id)
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        
        # Check if agent has enough goods
        if good_name not in agent_state.goods or agent_state.goods[good_name] < quantity:
            # Reduce health when can't consume required goods
            agent_state.health -= 10
            return f"Cannot consume {quantity} {good_name}. You only have {agent_state.goods.get(good_name, 0)}. Health reduced to {agent_state.health}."
        
        # Consume goods
        # Check if agent has currency to pay for food (assume base price of 1.0 if not in market)
        food_price = ECONOMY.market_prices.get(good_name, 1.0)
        total_cost = food_price * quantity

        if agent_state.currency < total_cost:
            # Can't afford food, reduce health more severely
            agent_state.health -= 15
            return f"Cannot afford {quantity} {good_name} (costs {total_cost}, you have {agent_state.currency}). Health reduced to {agent_state.health}."

        # Consume goods and deduct currency
        agent_state.goods[good_name] -= quantity
        agent_state.currency -= total_cost
        agent_state.health = min(100, agent_state.health + 5)  # Consuming food increases health

        return f"Consumed {quantity} {good_name} for {total_cost} currency. You now have {agent_state.goods[good_name]} units. Currency: {agent_state.currency}, Health: {agent_state.health}."

class CreateOfferTool:
    """Tool to create selling offers"""
    
    def run(self, agent_id: str, good_name: str, quantity: int, price: float) -> str:
        """Create an offer to sell goods"""
        agent_state = ECONOMY.get_agent_state(agent_id)
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        
        # Check if agent has enough goods
        if good_name not in agent_state.goods or agent_state.goods[good_name] < quantity:
            return f"Cannot create offer. You only have {agent_state.goods.get(good_name, 0)} units of {good_name}."
        
        # Create offer
        offer = Offer(
            seller_id=agent_id,
            good_name=good_name,
            quantity=quantity,
            price=price
        )
        
        ECONOMY.offers.append(offer)
        
        return f"Created offer {offer.offer_id} to sell {quantity} {good_name} at {price} each."

class CreateRequestTool:
    """Tool to create buy requests"""
    
    def run(self, agent_id: str, good_name: str, quantity: int, max_price: float) -> str:
        # Check if agent has enough currency
        total_cost = max_price * quantity
        agent_state = ECONOMY.get_agent_state(agent_id) 

        if agent_state.currency < total_cost:
            return f"Cannot create request. You only have {agent_state.currency} currency, but need {total_cost}."

        # Reserve the currency for this request
        agent_state.currency -= total_cost

        # Create request
        request = Request(
            buyer_id=agent_id,
            good_name=good_name,
            quantity=quantity,
            max_price=max_price
        )

        ECONOMY.requests.append(request)

        return f"Created request {request.request_id} to buy {quantity} {good_name} at max {max_price} each. Reserved {total_cost} currency."

class ViewMarketTool:
    """Tool to view current market offers and requests"""
    
    def run(self, agent_id: str) -> str:
        """Get current market information"""
        offers_str = "\nCurrent Offers:\n"
        if ECONOMY.offers:
            for offer in ECONOMY.offers:
                offers_str += f"- {offer.offer_id}: {offer.quantity} {offer.good_name} at {offer.price} each from {offer.seller_id}\n"
        else:
            offers_str += "- No offers available\n"
        
        requests_str = "\nCurrent Requests:\n"
        if ECONOMY.requests:
            for request in ECONOMY.requests:
                requests_str += f"- {request.request_id}: {request.quantity} {request.good_name} at max {request.max_price} each from {request.buyer_id}\n"
        else:
            requests_str += "- No requests available\n"
        
        market_prices = "\nMarket Prices:\n"
        if ECONOMY.market_prices:
            for good, price in ECONOMY.market_prices.items():
                market_prices += f"- {good}: {price}\n"
        else:
            market_prices += "- No market prices established yet\n"
        
        return offers_str + requests_str + market_prices

class CheckInventoryTool:
    """Tool to check agent's inventory"""
    
    def run(self, agent_id: str) -> str:
        """Get agent's current inventory and status"""
        agent_state = ECONOMY.get_agent_state(agent_id)
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        
        inventory = f"Currency: {agent_state.currency}\nHealth: {agent_state.health}\nGoods:"
        
        if agent_state.goods:
            for good, quantity in agent_state.goods.items():
                inventory += f"\n- {good}: {quantity}"
        else:
            inventory += "\n- No goods in inventory"
        
        return inventory

class AcceptOfferTool:
    """Tool to accept selling offers"""
    
    def run(self, agent_id: str, offer_id: str) -> str:
        """Accept an offer to buy goods"""
        agent_state = ECONOMY.get_agent_state(agent_id)
        if not agent_state:
            return f"Error: Agent {agent_id} not found. Make sure you are using your correct agent_id."
        
        # Find the offer
        offer = next((o for o in ECONOMY.offers if o.offer_id == offer_id), None)
        if not offer:
            return f"Error: Offer {offer_id} not found. Available offers: {[o.offer_id for o in ECONOMY.offers]}"
        
        # Check if buyer has enough currency
        total_cost = offer.price * offer.quantity
        if agent_state.currency < total_cost:
            return f"Cannot accept offer. You only have {agent_state.currency} currency, but need {total_cost}."
        # Add logging
        
        
        # Find seller
        seller_state = ECONOMY.get_agent_state(offer.seller_id)
        if not seller_state:
            return f"Error: Seller {offer.seller_id} not found"
        
        # Check if seller still has goods
        if offer.good_name not in seller_state.goods or seller_state.goods[offer.good_name] < offer.quantity:
            return f"Error: Seller no longer has enough {offer.good_name}"
        
        # Transfer goods and currency
        seller_state.goods[offer.good_name] -= offer.quantity
        seller_state.currency += total_cost
        
        if offer.good_name not in agent_state.goods:
            agent_state.goods[offer.good_name] = 0
        agent_state.goods[offer.good_name] += offer.quantity
        agent_state.currency -= total_cost
        
        # Record transaction
        transaction = Transaction(
            seller_id=offer.seller_id,
            buyer_id=agent_id,
            good_name=offer.good_name,
            quantity=offer.quantity,
            price=offer.price
        )
        ECONOMY.transactions.append(transaction)
        
        # Remove the offer
        ECONOMY.offers = [o for o in ECONOMY.offers if o.offer_id != offer_id]
        
        # Update market price
        ECONOMY.update_market_price(offer.good_name, offer.price)
        
        return f"Accepted offer {offer_id}. Bought {offer.quantity} {offer.good_name} for {total_cost} currency. Remaining currency: {agent_state.currency}."

class AcceptRequestTool:
    """Tool to accept buy requests"""
    
    def run(self, agent_id: str, request_id: str) -> str:
        """Accept a request to sell goods"""
        agent_state = ECONOMY.get_agent_state(agent_id)
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        
        # Find the request
        request = next((r for r in ECONOMY.requests if r.request_id == request_id), None)
        if not request:
            return f"Error: Request {request_id} not found"
        
        # Check if seller has enough goods
        if request.good_name not in agent_state.goods or agent_state.goods[request.good_name] < request.quantity:
            return f"Cannot accept request. You only have {agent_state.goods.get(request.good_name, 0)} units of {request.good_name}."
        
        # Find buyer
        buyer_state = ECONOMY.get_agent_state(request.buyer_id)
        if not buyer_state:
            return f"Error: Buyer {request.buyer_id} not found"
        
        # Check if buyer still has enough currency
        total_cost = request.max_price * request.quantity
        if buyer_state.currency < total_cost:
            return f"Error: Buyer no longer has enough currency"
        
        # Transfer goods and currency
        agent_state.goods[request.good_name] -= request.quantity
        agent_state.currency += total_cost
        
        if request.good_name not in buyer_state.goods:
            buyer_state.goods[request.good_name] = 0
        buyer_state.goods[request.good_name] += request.quantity
        buyer_state.currency -= total_cost
        
        # Record transaction
        transaction = Transaction(
            seller_id=agent_id,
            buyer_id=request.buyer_id,
            good_name=request.good_name,
            quantity=request.quantity,
            price=request.max_price
        )
        ECONOMY.transactions.append(transaction)
        
        # Remove the request
        ECONOMY.requests = [r for r in ECONOMY.requests if r.request_id != request_id]
        
        # Update market price
        ECONOMY.update_market_price(request.good_name, request.max_price)
        
        return f"Accepted request {request_id}. Sold {request.quantity} {request.good_name} for {total_cost} currency."

class OfferLaborTool:
    """Tool to offer labor to other agents"""
    
    def run(self, agent_id: str, target_agent_id: str, labor_units: int, price_per_unit: float) -> str:
        """Offer labor to another agent"""
        agent_state = ECONOMY.get_agent_state(agent_id)
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        
        # Check if agent has enough labor capacity
        available_labor = agent_state.labor_capacity - agent_state.labor_used
        if available_labor < labor_units:
            return f"Cannot offer labor. You only have {available_labor} labor units available."
        
        # Find target agent
        target_agent = ECONOMY.get_agent_state(target_agent_id)
        if not target_agent:
            return f"Error: Target agent {target_agent_id} not found"
        
        # Create a special type of offer for labor
        offer = Offer(
            seller_id=agent_id,
            good_name="labor",
            quantity=labor_units,
            price=price_per_unit
        )
        
        ECONOMY.offers.append(offer)
        
        return f"Created labor offer {offer.offer_id} to provide {labor_units} labor units to {target_agent_id} at {price_per_unit} each."

class HireLaborTool:
    """Tool to hire labor from other agents"""
    
    def run(self, agent_id: str, offer_id: str) -> str:
        """Hire labor from another agent"""
        agent_state = ECONOMY.get_agent_state(agent_id)
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        
        # Find the labor offer
        offer = next((o for o in ECONOMY.offers if o.offer_id == offer_id and o.good_name == "labor"), None)
        if not offer:
            return f"Error: Labor offer {offer_id} not found"
        
        # Check if employer has enough currency
        total_cost = offer.price * offer.quantity
        if agent_state.currency < total_cost:
            return f"Cannot hire labor. You only have {agent_state.currency} currency, but need {total_cost}."
        
        # Find worker
        worker_state = ECONOMY.get_agent_state(offer.seller_id)
        if not worker_state:
            return f"Error: Worker {offer.seller_id} not found"
        
        # Check if worker still has labor capacity
        available_labor = worker_state.labor_capacity - worker_state.labor_used
        if available_labor < offer.quantity:
            return f"Error: Worker no longer has enough labor capacity"
        
        # Transfer currency and update labor used
        worker_state.currency += total_cost
        worker_state.labor_used += offer.quantity
        agent_state.currency -= total_cost
        
        # Record transaction
        transaction = Transaction(
            seller_id=offer.seller_id,
            buyer_id=agent_id,
            good_name="labor",
            quantity=offer.quantity,
            price=offer.price
        )
        ECONOMY.transactions.append(transaction)
        
        # Remove the offer
        ECONOMY.offers = [o for o in ECONOMY.offers if o.offer_id != offer_id]
        
        # Add a small production boost for the employer
        for good_name in agent_state.goods:
            boost_amount = int(offer.quantity * 0.5)  # Each labor unit increases production by 0.5
            agent_state.goods[good_name] += boost_amount
            
        return f"Hired {offer.quantity} labor units from {offer.seller_id} for {total_cost} currency. Production increased."

class MarketMatchTool:
    """Tool for Market Agent to match offers and requests"""
    
    def run(self, agent_id: str) -> str:
        """Match compatible offers and requests"""
        matches_made = 0
        transactions_log = ""
        
        # Copy lists to avoid modification during iteration
        offers = ECONOMY.offers.copy()
        requests = ECONOMY.requests.copy()
        
        for offer in offers:
            matching_requests = [r for r in requests if r.good_name == offer.good_name 
                               and r.max_price >= offer.price
                               and r.quantity <= offer.quantity]
            
            if matching_requests:
                # Sort by price (highest first) to maximize market agent profit
                matching_requests.sort(key=lambda r: r.max_price, reverse=True)
                request = matching_requests[0]
                
                # Find buyer and seller
                buyer_state = ECONOMY.get_agent_state(request.buyer_id)
                seller_state = ECONOMY.get_agent_state(offer.seller_id)
                
                if not buyer_state or not seller_state:
                    continue
                
                # Calculate transaction details first
                quantity = min(offer.quantity, request.quantity)
                # Use the market price as an average between offer and request
                actual_price = (offer.price + request.max_price) / 2
                total_cost = actual_price * quantity
                
                # Market takes a small fee
                market_fee = total_cost * 0.05  # 5% fee
                seller_amount = total_cost - market_fee
                
                # Check if conditions are still valid
                # For seller: check if they have enough goods
                if (offer.good_name not in seller_state.goods or 
                    seller_state.goods[offer.good_name] < quantity):
                    continue
                
                # For buyer: Since currency was reserved when creating request,
                # we need to check if they have enough reserved currency
                # The buyer should have already reserved: request.max_price * request.quantity
                reserved_amount = request.max_price * quantity
                
                # Calculate refund (if actual price is lower than max price)
                refund_amount = reserved_amount - total_cost
                
                # Buyer should have non-negative currency after getting refund
                if buyer_state.currency + refund_amount < 0:
                    # This shouldn't happen if currency reservation worked properly
                    continue
                
                # Transfer goods and currency
                seller_state.goods[offer.good_name] -= quantity
                seller_state.currency += seller_amount
                
                if offer.good_name not in buyer_state.goods:
                    buyer_state.goods[offer.good_name] = 0
                buyer_state.goods[offer.good_name] += quantity
                
                # Give refund to buyer (they already had currency deducted when creating request)
                # If actual price equals max price, refund is 0
                buyer_state.currency += refund_amount
                
                # Add market fee to market agent
                market_agent = ECONOMY.get_agent_state(agent_id)
                if market_agent:
                    market_agent.currency += market_fee
                
                # Record transaction
                transaction = Transaction(
                    seller_id=offer.seller_id,
                    buyer_id=request.buyer_id,
                    good_name=offer.good_name,
                    quantity=quantity,
                    price=actual_price,
                    facilitated_by_market=True
                )
                ECONOMY.transactions.append(transaction)
                
                # Update market price
                ECONOMY.update_market_price(offer.good_name, actual_price)
                
                # Remove or update the offer and request
                if quantity == offer.quantity:
                    ECONOMY.offers = [o for o in ECONOMY.offers if o.offer_id != offer.offer_id]
                else:
                    for o in ECONOMY.offers:
                        if o.offer_id == offer.offer_id:
                            o.quantity -= quantity
                
                if quantity == request.quantity:
                    ECONOMY.requests = [r for r in ECONOMY.requests if r.request_id != request.request_id]
                else:
                    for r in ECONOMY.requests:
                        if r.request_id == request.request_id:
                            r.quantity -= quantity
                
                matches_made += 1
                transactions_log += f"Matched: {quantity} {offer.good_name} from {offer.seller_id} to {request.buyer_id} at {actual_price} each (market fee: {market_fee:.2f}, buyer refund: {refund_amount:.2f})\n"
                
                # Remove these from our working copies to avoid duplicate matches
                requests = [r for r in requests if r.request_id != request.request_id]
        
        if matches_made > 0:
            total_fees = sum(
            tx.price * tx.quantity * 0.05
            for tx in ECONOMY.transactions
            if tx.facilitated_by_market
            )

            return (
                f"Made {matches_made} matches:\n{transactions_log}"
                f"Total market fees collected: {total_fees:.2f}"
            )
        else:
            return "No matching offers and requests found."

class ResetLaborTool:
    """Tool to reset labor capacity for all agents at the end of a cycle"""
    
    def run(self) -> str:
        """Reset labor used for all agents"""
        for agent_id, agent_state in ECONOMY.agents.items():
            agent_state.labor_used = 0
        
        return "Reset labor capacity for all agents."

# --- Define CrewAI-native tools via decorator ---

@tool("Produce Food")
def produce_food_tool(agent_id: str) -> str:
    """Produce food units.
        Args:
            agent_id (str): Your agent identifier (must be 'producer')
            
        Returns:
            str: Result of production operation
    """
    return ProduceTool("food").run(agent_id)

@tool("Consume Food")
def consume_food_tool(agent_id: str, good_name: str = "food", quantity: int = 1) -> str:
    """Consume goods to restore health.
        Args:
            agent_id (str): Your agent identifier (must be 'consumer')
            
        Returns:
            str: Result of production operation
    """
    return ConsumeTool().run(agent_id, good_name, quantity)

@tool("Create Sell Offer")
def create_sell_offer_tool(agent_id: str, good_name: str, quantity: int, price: float) -> str:
    """
    Create an offer to sell goods.
    
    Args:
        agent_id (str): Your agent identifier (e.g., 'producer', 'trader')
        good_name (str): The name of the good to sell (e.g., 'food')
        quantity (int): Number of units to sell (must be > 0)
        price (float): Price per unit (must be > 0)
    
    Returns:
        str: Result of creating the offer with its offer_id if successful
    """
    return CreateOfferTool().run(agent_id, good_name, quantity, price)

@tool("Create Buy Request")
def create_buy_request_tool(agent_id: str, good_name: str, quantity: int, max_price: float) -> str:
    """
    Create a request to buy goods.
    
    Args:
        agent_id (str): Your agent identifier (e.g., 'consumer', 'trader')
        good_name (str): The name of the good to buy (e.g., 'food')
        quantity (int): Number of units to buy (must be > 0)
        max_price (float): Maximum price you're willing to pay per unit
    
    Returns:
        str: Result of creating the request with its request_id if successful
    """
    return CreateRequestTool().run(agent_id, good_name, quantity, max_price)

@tool("View Market")
def view_market_tool(agent_id: str) -> str:
    """
    View current market offers and requests.
    
    Args:
        agent_id (str): Your agent identifier
    
    Returns:
        str: Current market information including all offers, requests, and market prices
    """
    return ViewMarketTool().run(agent_id)

@tool("Check Inventory")
def check_inventory_tool(agent_id: str) -> str:
    """
    Check your inventory and status.
    
    Args:
        agent_id (str): Your agent identifier
    
    Returns:
        str: Your current inventory, currency, health, and other status information
    """
    return CheckInventoryTool().run(agent_id)

@tool("Accept Sell Offer")
def accept_sell_offer_tool(agent_id: str, offer_id: str) -> str:
    """
    Accept a selling offer to purchase goods from another agent.
    
    Args:
        agent_id (str): Your agent identifier (the buyer)
        offer_id (str): The ID of the offer to accept (e.g., 'offer_1234')
    
    Returns:
        str: Result of the transaction
    
    Note: You must have enough currency to complete the purchase
    """
    return AcceptOfferTool().run(agent_id, offer_id)

@tool("Accept Buy Request")
def accept_buy_request_tool(agent_id: str, request_id: str) -> str:
    """
    Accept a buy request to sell goods to another agent.
    
    Args:
        agent_id (str): Your agent identifier (the seller)
        request_id (str): The ID of the request to accept (e.g., 'request_1234')
    
    Returns:
        str: Result of the transaction
    
    Note: You must have enough of the requested goods to complete the sale
    """
    return AcceptRequestTool().run(agent_id, request_id)

@tool("Offer Labor")
def offer_labor_tool(agent_id: str, target_agent_id: str, labor_units: int, price_per_unit: float) -> str:
    """
    Offer labor to another agent.
    
    Args:
        agent_id (str): Your agent identifier (the worker)
        target_agent_id (str): The agent you want to offer labor to (e.g., 'producer')
        labor_units (int): Number of labor units to offer (must be > 0)
        price_per_unit (float): Price requested per labor unit
    
    Returns:
        str: Result of creating the labor offer with its offer_id if successful
    
    Note: You must have enough available labor capacity
    """
    return OfferLaborTool().run(agent_id, target_agent_id, labor_units, price_per_unit)

@tool("Hire Labor")
def hire_labor_tool(agent_id: str, offer_id: str) -> str:
    """
    Hire labor to boost production.
    
    Args:
        agent_id (str): Your agent identifier (the employer)
        offer_id (str): The ID of the labor offer to accept (e.g., 'offer_1234')
    
    Returns:
        str: Result of hiring labor and its effect on production
    
    Note: Hiring labor will increase your production capacity but costs currency
    """
    return HireLaborTool().run(agent_id, offer_id)

@tool("Match Market")
def match_market_tool(agent_id: str) -> str:
    """
    Match compatible offers and requests in the market.
    
    Args:
        agent_id (str): Your agent identifier (should be 'market')
    
    Returns:
        str: Summary of matches made and transactions facilitated
    
    Note: This tool is primarily for the market agent to facilitate trades
    """
    return MarketMatchTool().run(agent_id)

@tool("Track Currency")
def track_currency_tool(agent_id: str) -> str:
    """
    Track currency changes and transactions for debugging.
    
    Args:
        agent_id (str): Your agent identifier
    
    Returns:
        str: Detailed currency information and recent transactions
    """
    agent_state = ECONOMY.get_agent_state(agent_id)
    if not agent_state:
        return f"Error: Agent {agent_id} not found"
    
    # Get recent transactions involving this agent
    recent_transactions = []
    for tx in ECONOMY.transactions[-5:]:  # Last 5 transactions
        if tx.buyer_id == agent_id or tx.seller_id == agent_id:
            role = "buyer" if tx.buyer_id == agent_id else "seller"
            recent_transactions.append(f"{role} in {tx.transaction_id}: {tx.quantity} {tx.good_name} at {tx.price} each")
    
    result = f"Currency: {agent_state.currency}\n"
    if recent_transactions:
        result += "Recent transactions:\n" + "\n".join(recent_transactions)
    else:
        result += "No recent transactions"
    
    return result

# --- Re-define agents with BaseTool instances ---

producer_agent = Agent(
    role="Food Producer",
    goal="Maximize profit by producing and selling food",
    backstory="You are a farmer who produces food. Your goal is to maximize your profit by selling surplus food.",
    verbose=True,
    allow_delegation=False,
    tools=[
        produce_food_tool,
        consume_food_tool,
        create_sell_offer_tool,
        accept_buy_request_tool,
        check_inventory_tool,
        view_market_tool,
        hire_labor_tool,
    ],
)

consumer_agent = Agent(
    role="Food Consumer",
    goal="Maintain health by consuming food regularly",
    backstory="You need to consume food to survive. Your goal is to maintain your health by ensuring a steady supply of food.",
    verbose=True,
    allow_delegation=False,
    tools=[
        consume_food_tool,
        create_buy_request_tool,
        accept_sell_offer_tool,
        check_inventory_tool,
        view_market_tool,
    ],
)

market_agent = Agent(
    role="Market Facilitator",
    goal="Facilitate trades and maximize fees collected",
    backstory="You run the market where producers and consumers trade. Your goal is to facilitate trades and collect fees.",
    verbose=True,
    allow_delegation=False,
    tools=[
        match_market_tool,
        view_market_tool,
        check_inventory_tool,
    ],
)

worker_agent = Agent(
    role="Labor Provider",
    goal="Earn currency by offering labor services",
    backstory="You offer your labor to help others produce more. Your goal is to earn enough to survive and save a little.",
    verbose=True,
    allow_delegation=False,
    tools=[
        consume_food_tool,
        offer_labor_tool,
        create_buy_request_tool,
        accept_sell_offer_tool,
        check_inventory_tool,
        view_market_tool,
    ],
)

trader_agent = Agent(
    role="Goods Trader",
    goal="Maximize profit by buying low and selling high",
    backstory="You buy goods when prices are low and sell them when prices are high. Your goal is to maximize profit over time.",
    verbose=True,
    allow_delegation=False,
    tools=[
        consume_food_tool,
        create_buy_request_tool,
        create_sell_offer_tool,
        accept_sell_offer_tool,
        accept_buy_request_tool,
        check_inventory_tool,
        view_market_tool,
    ],
)

# Define the tasks

# Initialize the economy
def initialize_economy():
    """Initialize the economy and agent states"""
    # Create agent states
    ECONOMY.add_agent("producer")
    ECONOMY.add_agent("consumer")
    ECONOMY.add_agent("market")
    ECONOMY.add_agent("worker")
    ECONOMY.add_agent("trader")
    
    # Initialize producer with some food
    producer_state = ECONOMY.get_agent_state("producer")
    producer_state.goods["food"] = 5
    
    # Give all consumer-type agents some initial food to avoid health loss in first cycle
    consumer_state = ECONOMY.get_agent_state("consumer")
    consumer_state.goods["food"] = 2
    
    worker_state = ECONOMY.get_agent_state("worker")
    worker_state.goods["food"] = 2
    
    trader_state = ECONOMY.get_agent_state("trader")
    trader_state.goods["food"] = 2
    
    # Initialize market prices
    ECONOMY.update_market_price("food", 2.0)
    
    return "Economy initialized successfully."

# Producer Task
# Producer Task
producer_task = Task(
    description="""
    As a food producer, your job is to:
    
    1. Check your inventory: 
       - Use: Check Inventory (agent_id="producer")
       - Do this first to understand what resources you have
    
    2. Produce new food each cycle: 
       - Use: Produce Food (agent_id="producer")
       - This is your primary function - produce as much as possible
    
    3. Consume food to maintain your health: 
       - Use: Consume Food (agent_id="producer", good_name="food", quantity=1)
       - ALWAYS do this each cycle or your health will decrease
    
    4. Create offers to sell surplus food:
       - Use: Create Sell Offer (agent_id="producer", good_name="food", quantity=X, price=Y)
       - Sell any food beyond what you need to consume (keep 1-2 in reserve)
       - Example: Create Sell Offer (agent_id="producer", good_name="food", quantity=3, price=2.0)
    
    5. Accept any reasonable buy requests:
       - Use: Accept Buy Request (agent_id="producer", request_id="request_XXXX")
       - Check for requests with View Market (agent_id="producer")
       - Accept requests with prices at or above the market average
    
    6. Consider hiring workers to boost production:
       - Use: Hire Labor (agent_id="producer", offer_id="offer_XXXX")
       - View labor offers with View Market (agent_id="producer")
       - Only hire if you have surplus currency and the price is reasonable
    
    IMPORTANT: 
    - Your agent_id is "producer" - always use this in all tool calls
    - You MUST consume 1 food per cycle
    - Try to maintain at least 1-2 food in reserve
    - Make your decisions based on current market prices
    - Prioritize these actions in order: consume food, produce food, sell surplus
    
    Example decision sequence:
    1. Check your inventory to see current food and currency
    2. Produce new food to increase your stock
    3. Consume 1 food unit to maintain health
    4. View the market to see current prices
    5. Create sell offers for excess food (keeping 1-2 units in reserve)
    6. Check for and accept any profitable buy requests
    """,
    agent=producer_agent,
    expected_output="A summary of actions taken and current status",
)

# Consumer Task
consumer_task = Task(
    description="""
    As a food consumer, your job is to:
    
    1. Check your inventory:
       - Use: Check Inventory (agent_id="consumer")
       - Check how much food and currency you have
    
    2. Consume food to maintain health:
       - Use: Consume Food (agent_id="consumer", good_name="food", quantity=1)
       - CRITICAL: Do this EVERY cycle to avoid health penalties
    
    3. Create requests to buy food if needed:
       - Use: Create Buy Request (agent_id="consumer", good_name="food", quantity=X, max_price=Y)
       - Always maintain at least 2-3 food units in reserve
       - Example: Create Buy Request (agent_id="consumer", good_name="food", quantity=2, max_price=2.5)
    
    4. Accept reasonable offers to buy food:
       - Use: View Market (agent_id="consumer") to see available offers
       - Use: Accept Sell Offer (agent_id="consumer", offer_id="offer_XXXX")
       - Accept offers with prices at or below your maximum budget
    
    IMPORTANT:
    - Your agent_id is "consumer" - always use this in all tool calls
    - Your health will decrease by 15 points if you don't consume food each cycle
    - Your survival depends on maintaining a steady food supply
    - Budget your currency carefully to ensure you can always afford food
    
    Example decision sequence:
    1. Check your inventory to assess your food supply and currency
    2. Consume 1 food unit immediately
    3. View the market to check current food prices
    4. If food supply is below 3 units, create a buy request or accept an existing sell offer
    5. Always prioritize food security over saving currency
    """,
    agent=consumer_agent,
    expected_output="A summary of actions taken and current status",
)

# Market Task
market_task = Task(
    description="""
    As a market facilitator, your job is to:
    
    1. Check current market status:
       - Use: View Market (agent_id="market")
       - Analyze the available offers and requests
    
    2. Match compatible offers and requests:
       - Use: Match Market (agent_id="market")
       - This is your PRIMARY function - do this every cycle
    
    3. Monitor your earnings:
       - Use: Check Inventory (agent_id="market")
       - Track how much currency you've collected in fees
    
    IMPORTANT:
    - Your agent_id is "market" - always use this in all tool calls
    - You earn a 5% fee on all transactions you facilitate
    - Your goal is to create a balanced, efficient market
    - You should actively look for potential matches between buyers and sellers
    
    Example decision sequence:
    1. View the market to see all current offers and requests
    2. Run the matching algorithm to pair compatible trades
    3. Check your inventory to see how much you've earned in fees
    4. Provide a summary of market activity and any trades facilitated
    
    Tips for effective facilitation:
    - Look for offers and requests with compatible prices
    - Track price trends to identify market inefficiencies
    - Focus on ensuring all agents can access the resources they need
    """,
    agent=market_agent,
    expected_output="A detailed summary of market activity, trades facilitated, and fees collected",
)

# Worker Task
worker_task = Task(
    description="""
    As a labor provider, your job is to:
    
    1. Check your status and inventory:
       - Use: Check Inventory (agent_id="worker")
       - Assess your food supply and currency
    
    2. Consume food to maintain health:
       - Use: Consume Food (agent_id="worker", good_name="food", quantity=1)
       - CRITICAL: Do this EVERY cycle to avoid health penalties
    
    3. Offer your labor services:
       - Use: Offer Labor (agent_id="worker", target_agent_id="producer", labor_units=X, price_per_unit=Y)
       - Example: Offer Labor (agent_id="worker", target_agent_id="producer", labor_units=2, price_per_unit=1.5)
       - You can also offer labor to the trader with target_agent_id="trader"
    
    4. Buy food when needed:
       - Use: View Market (agent_id="worker") to check food prices
       - Use: Create Buy Request (agent_id="worker", good_name="food", quantity=X, max_price=Y)
       - Or: Accept Sell Offer (agent_id="worker", offer_id="offer_XXXX")
    
    IMPORTANT:
    - Your agent_id is "worker" - always use this in all tool calls
    - You must consume 1 food unit per cycle to maintain health
    - Your labor capacity resets each cycle (5 units available)
    - Set your labor price based on current market conditions
    
    Example decision sequence:
    1. Check your inventory to assess food and currency
    2. Consume 1 food unit immediately
    3. View the market to understand current food prices
    4. If food is low (below 2 units), buy more food
    5. Offer your labor at competitive prices
    6. If labor offers aren't being accepted, try lowering your price
    """,
    agent=worker_agent,
    expected_output="A summary of labor offered, food consumed, and overall status",
)

# Trader Task
trader_task = Task(
    description="""
    As a goods trader, your job is to:
    
    1. Check your inventory and status:
       - Use: Check Inventory (agent_id="trader")
       - Assess your current goods, food supply, and currency
    
    2. Consume food to maintain health:
       - Use: Consume Food (agent_id="trader", good_name="food", quantity=1)
       - CRITICAL: Do this EVERY cycle to maintain health
    
    3. Analyze market conditions:
       - Use: View Market (agent_id="trader")
       - Identify price trends and arbitrage opportunities
    
    4. Buy low:
       - Use: Create Buy Request (agent_id="trader", good_name="food", quantity=X, max_price=Y)
       - Example: Create Buy Request (agent_id="trader", good_name="food", quantity=3, max_price=1.8)
       - Or: Accept Sell Offer (agent_id="trader", offer_id="offer_XXXX")
       - Target prices below the current market average
    
    5. Sell high:
       - Use: Create Sell Offer (agent_id="trader", good_name="food", quantity=X, price=Y)
       - Example: Create Sell Offer (agent_id="trader", good_name="food", quantity=2, price=2.5)
       - Or: Accept Buy Request (agent_id="trader", request_id="request_XXXX")
       - Target prices above your purchase price plus a markup
    
    IMPORTANT:
    - Your agent_id is "trader" - always use this in all tool calls
    - You must consume 1 food unit per cycle
    - Keep at least 1-2 food in reserve for your own consumption
    - Your goal is to maximize profit through price arbitrage
    - You can hire labor to boost your operations if profitable
    
    Example decision sequence:
    1. Check inventory to assess current resources
    2. Consume 1 food unit immediately
    3. View the market to analyze price trends
    4. Buy goods when prices are below market average
    5. Sell goods when you can make a profit (typically 10-20% markup)
    6. Always ensure you have enough food for the next cycle
    """,
    agent=trader_agent,
    expected_output="A summary of trading activity, profits made, and current inventory",
)

# End of Cycle Task
def end_cycle():
    """End the current cycle and prepare for the next one"""
    ECONOMY.cycle += 1
    
    # Reset labor capacity
    ResetLaborTool().run()
    
    print(f"\n===== End of Cycle {ECONOMY.cycle - 1} =====")
    
    # Check which agents consumed food this cycle
    consumption_status = {agent_id: False for agent_id in ECONOMY.agents if agent_id != "market"}
    
    # Check transactions for food consumption
    for tx in ECONOMY.transactions:
        if tx.good_name == "food" and tx.buyer_id in consumption_status:
            consumption_status[tx.buyer_id] = True
    
    # Apply health changes based on food consumption
    for agent_id, consumed in consumption_status.items():
        agent_state = ECONOMY.get_agent_state(agent_id)
        
        # If agent didn't consume through transactions, try to use inventory
        if not consumed and "food" in agent_state.goods and agent_state.goods["food"] > 0:
            food_price = ECONOMY.market_prices.get("food", 1.0)
            if agent_state.currency >= food_price:
                agent_state.goods["food"] -= 1
                agent_state.currency -= food_price
                print(f"{agent_id} consumed 1 food from inventory for {food_price} currency")
                consumed = True
            else:
                print(f"{agent_id} has food but cannot afford to consume it (needs {food_price}, has {agent_state.currency})")
        
        # Apply health changes
        if consumed:
            agent_state.health = min(100, agent_state.health + 5)
            print(f"{agent_id} maintained health: {agent_state.health}")
        else:
            agent_state.health -= 15
            print(f"{agent_id} health decreased to: {agent_state.health} (no food consumed)")
            
            if agent_state.health < 0:
                agent_state.health = 0
    
    # Clear out old offers/requests and transactions
    ECONOMY.offers = []
    ECONOMY.requests = []
    ECONOMY.transactions = []
    
    print(f"Ended cycle {ECONOMY.cycle - 1}. Starting cycle {ECONOMY.cycle}.")
    return f"Ended cycle {ECONOMY.cycle - 1}. Starting cycle {ECONOMY.cycle}."

# Define the crew
economy_crew = Crew(
    agents=[producer_agent, consumer_agent, market_agent, worker_agent, trader_agent],
    tasks=[producer_task, consumer_task, market_task, worker_task, trader_task],
    verbose=True,
    process=Process.sequential,  # Run tasks in sequence
)

# Main simulation function
def run_simulation(cycles=5,save_file: str = "economy_state.json", resume: bool = False):
    """Run the economic simulation for a specified number of cycles"""
    global ECONOMY

    if resume and os.path.exists(save_file):
        ECONOMY = EconomyState.load(save_file)
    else:
        initialize_economy()
    
    results = []
    
    for cycle in range(cycles):
        print(f"\n===== Starting Cycle {cycle + 1} =====")
        
        # Run the crew for this cycle
        cycle_results = economy_crew.kickoff()
        results.append(cycle_results)
        
        # End the cycle
        end_cycle()
        
        # Print cycle summary
        print("\n===== Cycle Summary =====")
        for agent_id, state in ECONOMY.agents.items():
            print(f"{agent_id}: Health={state.health}, Currency={state.currency}, Goods={state.goods}")
    
    ECONOMY.save(save_file)
    
    return results

# Run the simulation if this script is executed directly
if __name__ == "__main__":
    run_simulation(3)
 