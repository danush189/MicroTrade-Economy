from models import EconomyState, Offer, Request, Transaction, AgentState
from crewai.tools import tool

# Global economy state (set by main.py at runtime)
ECONOMY = None

# Tool classes for the modular micro trade economy

class ProduceTool:
    """Tool to produce goods"""
    def __init__(self, good_name: str, production_rate: int = 1):
        self.good_name = good_name
        self.production_rate = production_rate
    def run(self, agent_id: str) -> str:
        agent_state = ECONOMY.get_agent_state(agent_id) if ECONOMY else None
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        if self.good_name not in agent_state.goods:
            agent_state.goods[self.good_name] = 0
        agent_state.goods[self.good_name] += self.production_rate
        ECONOMY.log_agent_decision(agent_id, f"Produced {self.production_rate} units of {self.good_name}. Total: {agent_state.goods[self.good_name]}")
        return f"Produced {self.production_rate} units of {self.good_name}. You now have {agent_state.goods[self.good_name]} units."

class ConsumeTool:
    """Tool to consume goods and affect agent's health and currency"""
    def run(self, agent_id: str, good_name: str, quantity: int = 1) -> str:
        agent_state = ECONOMY.get_agent_state(agent_id) if ECONOMY else None
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        if good_name not in agent_state.goods or agent_state.goods[good_name] < quantity:
            agent_state.health -= 10
            ECONOMY.log_agent_decision(agent_id, f"FAILED to consume {quantity} {good_name} - insufficient goods. Health reduced to {agent_state.health}")
            return f"Cannot consume {quantity} {good_name}. You only have {agent_state.goods.get(good_name, 0)}. Health reduced to {agent_state.health}."
        food_price = ECONOMY.market_prices.get(good_name, 1.0)
        total_cost = food_price * quantity
        if agent_state.currency < total_cost:
            agent_state.health -= 15
            return f"Cannot afford {quantity} {good_name} (costs {total_cost}, you have {agent_state.currency}). Health reduced to {agent_state.health}."
        agent_state.goods[good_name] -= quantity
        agent_state.currency -= total_cost
        agent_state.health = min(100, agent_state.health + 5)
        ECONOMY.log_agent_decision(agent_id, f"Consumed {quantity} {good_name} for {total_cost} currency. Health: {agent_state.health}, Currency: {agent_state.currency}")
        return f"Consumed {quantity} {good_name} for {total_cost} currency. You now have {agent_state.goods[good_name]} units. Currency: {agent_state.currency}, Health: {agent_state.health}."

class CreateOfferTool:
    """Tool to create a sell offer for goods"""
    def run(self, agent_id: str, good_name: str, quantity: int, price: float) -> str:
        agent_state = ECONOMY.get_agent_state(agent_id) if ECONOMY else None
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        if good_name not in agent_state.goods or agent_state.goods[good_name] < quantity:
            return f"Cannot create offer. You only have {agent_state.goods.get(good_name, 0)} units of {good_name}."
        offer = Offer(
            seller_id=agent_id,
            good_name=good_name,
            quantity=quantity,
            price=price
        )
        ECONOMY.offers.append(offer)
        ECONOMY.log_agent_decision(agent_id, f"Created sell offer {offer.offer_id}: {quantity} {good_name} @ {price} each")
        return f"Created offer {offer.offer_id} to sell {quantity} {good_name} at {price} each."

class CreateRequestTool:
    """Tool to create a buy request for goods"""
    def run(self, agent_id: str, good_name: str, quantity: int, max_price: float) -> str:
        total_cost = max_price * quantity
        agent_state = ECONOMY.get_agent_state(agent_id) if ECONOMY else None
        if agent_state.currency < total_cost:
            ECONOMY.log_agent_decision(agent_id, f"FAILED to create buy request - insufficient currency. Needed {total_cost}, have {agent_state.currency}")
            return f"Cannot create request. You only have {agent_state.currency} currency, but need {total_cost}."
        agent_state.currency -= total_cost
        request = Request(
            buyer_id=agent_id,
            good_name=good_name,
            quantity=quantity,
            max_price=max_price
        )
        ECONOMY.requests.append(request)
        ECONOMY.log_agent_decision(agent_id, f"Created buy request {request.request_id}: {quantity} {good_name} @ max {max_price} each. Reserved {total_cost} currency")
        return f"Created request {request.request_id} to buy {quantity} {good_name} at max {max_price} each. Reserved {total_cost} currency."

class ViewMarketTool:
    """Tool to view current market offers, requests, and prices"""
    def run(self, agent_id: str) -> str:
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
    """Tool to check the agent's own inventory"""
    def run(self, agent_id: str) -> str:
        agent_state = ECONOMY.get_agent_state(agent_id) if ECONOMY else None
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
    """Tool to accept an offer from another agent"""
    def run(self, agent_id: str, offer_id: str) -> str:
        agent_state = ECONOMY.get_agent_state(agent_id) if ECONOMY else None
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        offer = next((o for o in ECONOMY.offers if o.offer_id == offer_id), None)
        if not offer:
            return f"Offer {offer_id} not found"
        if agent_state.currency < offer.price:
            return f"Cannot accept offer. You need {offer.price} currency, but have {agent_state.currency}."
        agent_state.currency -= offer.price
        agent_state.goods[offer.good_name] = agent_state.goods.get(offer.good_name, 0) + offer.quantity
        ECONOMY.offers.remove(offer)
        ECONOMY.log_agent_decision(agent_id, f"Accepted offer {offer_id}: {offer.quantity} {offer.good_name} @ {offer.price} each")
        return f"Accepted offer {offer_id}: Received {offer.quantity} {offer.good_name}. Currency left: {agent_state.currency}"

class AcceptRequestTool:
    """Tool to accept a request from another agent"""
    def run(self, agent_id: str, request_id: str) -> str:
        agent_state = ECONOMY.get_agent_state(agent_id) if ECONOMY else None
        if not agent_state:
            return f"Error: Agent {agent_id} not found"
        request = next((r for r in ECONOMY.requests if r.request_id == request_id), None)
        if not request:
            return f"Request {request_id} not found"
        total_cost = request.max_price * request.quantity
        if agent_state.goods.get(request.good_name, 0) < request.quantity:
            return f"Cannot accept request. You need {request.quantity} {request.good_name}, but have {agent_state.goods.get(request.good_name, 0)}."
        agent_state.goods[request.good_name] -= request.quantity
        agent_state.currency += total_cost
        ECONOMY.requests.remove(request)
        ECONOMY.log_agent_decision(agent_id, f"Accepted request {request_id}: Sold {request.quantity} {request.good_name} @ max {request.max_price} each")
        return f"Accepted request {request_id}: Sold {request.quantity} {request.good_name}. Currency: {agent_state.currency}, Goods left: {agent_state.goods.get(request.good_name, 0)}"

class OfferLaborTool:
    """Tool to offer labor for a specified wage"""
    def run(self, agent_id: str, target_agent_id: str, labor_units: int, price_per_unit: float) -> str:
        agent_state = ECONOMY.get_agent_state(agent_id) if ECONOMY else None
        if not agent_state:
            return f"Error: Agent {agent_id} not found"

        target_state = ECONOMY.get_agent_state(target_agent_id)
        if not target_state:
            return f"Error: Target agent {target_agent_id} not found"

        # Check if agent has enough labor capacity
        available_labor = agent_state.labor_capacity - agent_state.labor_used
        if available_labor < labor_units:
            return f"Cannot offer labor. You only have {available_labor} labor units available."

        # Create a special offer for labor
        offer = Offer(
            seller_id=agent_id,
            good_name="labor",
            quantity=labor_units,
            price=price_per_unit
        )
        ECONOMY.offers.append(offer)
        ECONOMY.log_agent_decision(agent_id, f"Offered {labor_units} labor units to {target_agent_id} at {price_per_unit} per unit")
        return f"Created labor offer {offer.offer_id} to provide {labor_units} labor units at {price_per_unit} each"

class HireLaborTool:
    """Tool to hire labor from other agents"""
    
    def calculate_production_boost(self, labor_units: int) -> int:
        """Calculate the production boost from hired labor"""
        base_boost = 2  # Base production increase per labor unit
        efficiency_multiplier = 1.5  # 50% efficiency bonus
        return int(labor_units * base_boost * efficiency_multiplier)
    
    def execute(self, agent_state, other_agent_state, labor_units: int) -> bool:
        cost_per_unit = 1.0
        if agent_state.currency > 10:
            cost_per_unit = 1.2
        elif agent_state.currency < 5:
            cost_per_unit = 0.8
            
        total_cost = cost_per_unit * labor_units
        production_boost = self.calculate_production_boost(labor_units)
        
        if agent_state.currency >= total_cost and agent_state.currency > total_cost * 2:
            agent_state.currency -= total_cost
            other_agent_state.currency += total_cost
            agent_state.labor_capacity += production_boost
            return True
        return False

class MarketMatchTool:
    """Tool for Market Agent to match offers and requests"""
    
    def adjust_market_price(self, good_name: str, trades: list) -> float:
        """Adjust market price based on supply and demand"""
        if not trades:
            return ECONOMY.market_prices.get(good_name, 1.0)
        
        # Calculate average trade price
        avg_price = sum(t.price for t in trades) / len(trades)
        current_price = ECONOMY.market_prices.get(good_name, avg_price)
        
        # Count supply and demand
        supply = sum(1 for o in ECONOMY.offers if o.good_name == good_name)
        demand = sum(1 for r in ECONOMY.requests if r.good_name == good_name)
        
        # Adjust price based on supply/demand imbalance
        if supply > demand:
            new_price = current_price * 0.95  # Price decreases when supply > demand
        elif demand > supply:
            new_price = current_price * 1.05  # Price increases when demand > supply
        else:
            new_price = avg_price  # Price stabilizes at market average
        
        # Ensure price doesn't change too drastically
        max_change = 0.2  # Maximum 20% change per cycle
        min_price = current_price * (1 - max_change)
        max_price = current_price * (1 + max_change)
        new_price = max(min_price, min(max_price, new_price))
        
        return new_price

    def run(self, agent_id: str) -> str:
        """Match compatible offers and requests with dynamic pricing"""
        if agent_id != "market":
            return "Error: Only the market agent can use this tool"

        matches_made = 0
        transactions_log = ""
        cycle_trades = []
        
        # Copy lists to avoid modification during iteration
        offers = sorted(ECONOMY.offers.copy(), key=lambda x: x.price)
        requests = sorted(ECONOMY.requests.copy(), key=lambda x: x.max_price, reverse=True)
        
        for offer in offers:
            matching_requests = [r for r in requests if r.good_name == offer.good_name 
                               and r.max_price >= offer.price
                               and r.quantity > 0
                               and offer.quantity > 0]
            
            for request in matching_requests:
                buyer_state = ECONOMY.get_agent_state(request.buyer_id)
                seller_state = ECONOMY.get_agent_state(offer.seller_id)
                if not buyer_state or not seller_state:
                    continue

                # Calculate optimal trade quantity and price
                quantity = min(offer.quantity, request.quantity)
                actual_price = (offer.price + request.max_price) / 2
                total_cost = actual_price * quantity
                market_fee = total_cost * 0.05
                seller_amount = total_cost - market_fee

                # Validate the trade
                if (offer.good_name not in seller_state.goods or 
                    seller_state.goods[offer.good_name] < quantity):
                    continue

                # Process the trade
                seller_state.goods[offer.good_name] -= quantity
                seller_state.currency += seller_amount
                
                if offer.good_name not in buyer_state.goods:
                    buyer_state.goods[offer.good_name] = 0
                buyer_state.goods[offer.good_name] += quantity
                
                # Market collects fee
                market_state = ECONOMY.get_agent_state("market")
                if market_state:
                    market_state.currency += market_fee
                
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
                cycle_trades.append(transaction)
                
                # Update quantities
                offer.quantity -= quantity
                request.quantity -= quantity
                
                matches_made += 1
                transactions_log += (f"Matched: {quantity} {offer.good_name} "
                                  f"from {offer.seller_id} to {request.buyer_id} "
                                  f"at {actual_price:.2f} each "
                                  f"(market fee: {market_fee:.2f})\n")

                # Stop if either party's quantity is fulfilled
                if request.quantity == 0:
                    requests.remove(request)
                if offer.quantity == 0:
                    break

        # Clean up completed trades
        ECONOMY.offers = [o for o in ECONOMY.offers if o.quantity > 0]
        ECONOMY.requests = [r for r in ECONOMY.requests if r.quantity > 0]
        
        # Update market prices based on trading activity
        for good_name in set(t.good_name for t in cycle_trades):
            good_trades = [t for t in cycle_trades if t.good_name == good_name]
            new_price = self.adjust_market_price(good_name, good_trades)
            ECONOMY.update_market_price(good_name, new_price)
            ECONOMY.log_agent_decision("market", f"Updated {good_name} price to {new_price:.2f}")

        if matches_made > 0:
            total_fees = sum(tx.price * tx.quantity * 0.05 for tx in cycle_trades)
            ECONOMY.log_agent_decision(agent_id, 
                f"Facilitated {matches_made} trades. Total fees collected: {total_fees:.2f}")
            return (f"Made {matches_made} matches:\n{transactions_log}"
                   f"Total market fees collected: {total_fees:.2f}")
        else:
            return "No matching offers and requests found."

    def match_market(self, economy_state):
        matched_requests = set()
        for request in list(economy_state.requests):
            buyer = economy_state.get_agent_state(request.buyer_id)
            if not buyer:
                continue
            # Find matching offer
            offer = next((o for o in economy_state.offers if o.good_name == request.good_name and o.price <= request.max_price and o.quantity >= request.quantity), None)
            if offer:
                seller = economy_state.get_agent_state(offer.seller_id)
                if seller and seller.goods.get(offer.good_name, 0) >= request.quantity:
                    # Execute trade
                    total_price = offer.price * request.quantity
                    if buyer.currency >= total_price:
                        buyer.currency -= total_price
                        seller.currency += total_price
                        buyer.goods[offer.good_name] = buyer.goods.get(offer.good_name, 0) + request.quantity
                        seller.goods[offer.good_name] -= request.quantity
                        # Log transaction
                        tx_msg = f"[Cycle {economy_state.cycle}] {buyer.agent_id} bought {request.quantity} {offer.good_name} from {seller.agent_id} for {total_price:.2f}"
                        economy_state.log_agent_decision(buyer.agent_id, tx_msg)
                        economy_state.log_agent_decision(seller.agent_id, tx_msg)
                        matched_requests.add(request.request_id)
                        # Remove offer if depleted
                        offer.quantity -= request.quantity
                        if offer.quantity <= 0:
                            economy_state.offers = [o for o in economy_state.offers if o.offer_id != offer.offer_id]
                    else:
                        # Not enough currency, refund and log
                        refund = request.max_price * request.quantity
                        buyer.currency += refund
                        fail_msg = f"[Cycle {economy_state.cycle}] {buyer.agent_id} failed to buy {request.quantity} {offer.good_name}: insufficient funds. Refunded {refund:.2f}"
                        economy_state.log_agent_decision(buyer.agent_id, fail_msg)
                        matched_requests.add(request.request_id)
                else:
                    # Seller doesn't have enough goods
                    refund = request.max_price * request.quantity
                    buyer.currency += refund
                    fail_msg = f"[Cycle {economy_state.cycle}] {buyer.agent_id} failed to buy {request.quantity} {offer.good_name}: seller out of stock. Refunded {refund:.2f}"
                    economy_state.log_agent_decision(buyer.agent_id, fail_msg)
                    matched_requests.add(request.request_id)
            else:
                # No matching offer found
                refund = request.max_price * request.quantity
                buyer.currency += refund
                fail_msg = f"[Cycle {economy_state.cycle}] {buyer.agent_id} failed to buy {request.quantity} {request.good_name}: no offer matched. Refunded {refund:.2f}"
                economy_state.log_agent_decision(buyer.agent_id, fail_msg)
                matched_requests.add(request.request_id)
        # Remove matched/failed requests
        economy_state.requests = [r for r in economy_state.requests if r.request_id not in matched_requests]

    def execute(self, request_state, offer_state, quantity: int, max_price: float) -> bool:
        # Dynamic pricing based on market conditions
        base_price = 1.0
        
        # Adjust price based on buyer's currency
        if request_state.currency < 5:
            base_price = 0.8
        
        # Anti-hoarding: Significant discount if seller has excess
        if offer_state.goods.get('food', 0) > 3:
            base_price *= 0.7
        
        # Calculate final price
        final_price = min(base_price, max_price, 1.5)  # Cap at 1.5
        total_cost = quantity * final_price
        
        if offer_state.goods.get('food', 0) >= quantity and request_state.currency >= total_cost:
            # Execute trade
            request_state.currency -= total_cost
            offer_state.currency += total_cost
            request_state.goods['food'] = request_state.goods.get('food', 0) + quantity
            offer_state.goods['food'] -= quantity
            return True
        return False

class ResetLaborTool:
    """Tool to reset labor capacity for all agents"""
    def run(self, agent_id: str) -> str:
        # Reset labor for all agents
        for agent_name, agent_state in ECONOMY.agents.items():
            agent_state.labor_used = 0
            agent_state.labor_offer = 0.0
            ECONOMY.log_agent_decision(agent_name, "Labor capacity reset")
        
        ECONOMY.log_agent_decision(agent_id, "Reset labor capacity for all agents")
        return "Labor capacity has been reset for all agents"

@tool("Produce Food")
def produce_food_tool(agent_id: str) -> str:
    """
    Produce food units.
    
    Args:
        agent_id (str): Your agent identifier (must be 'producer')
            
    Returns:
        str: Result of production operation
    """
    return ProduceTool("food").run(agent_id)

@tool("Consume Food")
def consume_food_tool(agent_id: str, good_name: str = "food", quantity: int = 1) -> str:
    """
    Consume goods from agent's inventory.
    
    Args:
        agent_id (str): Your agent identifier
        good_name (str): The name of the good to consume (default: 'food')
        quantity (int): Amount to consume (default: 1)
            
    Returns:
        str: Result of consumption operation, including health and currency changes
    """
    return ConsumeTool().run(agent_id, good_name, quantity)

@tool("Create Sell Offer")
def create_sell_offer_tool(agent_id: str, good_name: str, quantity: int, price: float) -> str:
    """
    Create an offer to sell goods.
    
    Args:
        agent_id (str): Your agent identifier
        good_name (str): The name of the good to sell
        quantity (int): Amount to sell
        price (float): Price per unit
            
    Returns:
        str: Result of creating the offer
    """
    return CreateOfferTool().run(agent_id, good_name, quantity, price)

@tool("Create Buy Request")
def create_buy_request_tool(agent_id: str, good_name: str, quantity: int, max_price: float) -> str:
    """
    Create a request to buy goods.
    
    Args:
        agent_id (str): Your agent identifier
        good_name (str): The name of the good to buy
        quantity (int): Amount to buy
        max_price (float): Maximum price willing to pay per unit
            
    Returns:
        str: Result of creating the buy request
    """
    return CreateRequestTool().run(agent_id, good_name, quantity, max_price)

@tool("View Market")
def view_market_tool(agent_id: str) -> str:
    """
    View current market offers, requests, and prices.
    
    Args:
        agent_id (str): Your agent identifier
            
    Returns:
        str: Current market information including offers, requests, and prices
    """
    return ViewMarketTool().run(agent_id)

@tool("Check Inventory")
def check_inventory_tool(agent_id: str) -> str:
    """
    Check agent's current inventory and status.
    
    Args:
        agent_id (str): Your agent identifier
            
    Returns:
        str: Current inventory information including currency, health, and goods
    """
    return CheckInventoryTool().run(agent_id)

@tool("Accept Sell Offer")
def accept_sell_offer_tool(agent_id: str, offer_id: str) -> str:
    """
    Accept an offer to buy goods from another agent.
    
    Args:
        agent_id (str): Your agent identifier (the buyer)
        offer_id (str): The ID of the offer to accept (e.g., 'offer_1234')
            
    Returns:
        str: Result of the transaction
    """
    return AcceptOfferTool().run(agent_id, offer_id)

@tool("Accept Buy Request")
def accept_buy_request_tool(agent_id: str, request_id: str) -> str:
    """
    Accept a request to sell goods to another agent.
    
    Args:
        agent_id (str): Your agent identifier (the seller)
        request_id (str): The ID of the request to accept (e.g., 'request_1234')
            
    Returns:
        str: Result of the transaction
    """
    return AcceptRequestTool().run(agent_id, request_id)

@tool("Offer Labor")
def offer_labor_tool(agent_id: str, target_agent_id: str, labor_units: int, price_per_unit: float) -> str:
    """
    Offer labor services to another agent.
    
    Args:
        agent_id (str): Your agent identifier (the worker)
        target_agent_id (str): The agent to offer labor to
        labor_units (int): Amount of labor units to offer
        price_per_unit (float): Price per unit of labor
            
    Returns:
        str: Result of creating the labor offer
    """
    return OfferLaborTool().run(agent_id, target_agent_id, labor_units, price_per_unit)

@tool("Hire Labor")
def hire_labor_tool(agent_id: str, offer_id: str) -> str:
    """
    Hire labor from another agent.
    
    Args:
        agent_id (str): Your agent identifier (the employer)
        offer_id (str): The ID of the labor offer to accept
            
    Returns:
        str: Result of hiring the labor
    """
    return HireLaborTool().run(agent_id, offer_id)

@tool("Match Market")
def match_market_tool(agent_id: str) -> str:
    """
    Match compatible offers and requests in the market.
    
    Args:
        agent_id (str): Your agent identifier (must be 'market')
            
    Returns:
        str: Summary of matches made and actions taken
    """
    return MarketMatchTool().run(agent_id)
