from tools import *
from crewai import Agent

# Modular agent definitions for the micro trade economy

producer_agent = Agent(
    role="Food Producer",
    goal="Maximize profit by producing and selling food while maintaining health",
    backstory="""You are a farmer who produces food. Your goal is to maximize profit by selling surplus food.
    IMPORTANT: Producing food without labor will reduce your health by 5 points.
    Using labor increases production and prevents health loss.
    You should always try to hire labor when available at reasonable prices (≤2.0 currency per unit).""",
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

market_agent= Agent(
    role="Market Facilitator",
    goal="Facilitate trades and maximize fees collected",
    backstory="You run the market where traders, workers and producers exchange goods. Your goal is to facilitate trades and collect fees.",
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
    goal="Earn currency by offering labor services while maintaining health",
    backstory="""You offer your labor to help producers be more efficient.
    Your labor helps producers create more food without health penalties.
    Adjust your labor price based on market conditions:
    - If your health or currency is low (< 50), offer lower prices (1.0-1.5)
    - If market is stable, maintain moderate prices (1.5-2.0)""",
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

class Producer:
    def decide(self, economy_state):
        # Produce food
        produced = 1
        self.goods['food'] = self.goods.get('food', 0) + produced
        # Hire labor if food < 3 or worker offers labor at <= 1.5
        worker = economy_state.get_agent_state('worker')
        if self.goods.get('food', 0) < 3 and worker and worker.labor_offer > 0 and self.currency >= worker.labor_offer:
            labor_units = min(worker.labor_capacity, int(self.currency // worker.labor_offer))
            if labor_units > 0:
                self.currency -= labor_units * worker.labor_offer
                worker.currency += labor_units * worker.labor_offer
                self.goods['food'] += labor_units  # Each labor unit produces 1 food
                worker.labor_capacity -= labor_units
                economy_state.log_agent_decision(self.agent_id, f"Hired {labor_units} labor from worker at {worker.labor_offer} each.")
                economy_state.log_agent_decision(worker.agent_id, f"Sold {labor_units} labor to producer at {worker.labor_offer} each.")
        # Create sell offer if food > 2
        if self.goods.get('food', 0) > 2:
            offer_qty = self.goods['food'] - 2
            offer_price = 1.5
            economy_state.offers.append(Offer(seller_id=self.agent_id, good_name='food', quantity=offer_qty, price=offer_price))
            economy_state.log_agent_decision(self.agent_id, f"Created sell offer: {offer_qty} food @ {offer_price} each.")

class Worker:
    def decide(self, economy_state):
        # Offer labor at a competitive price
        self.labor_offer = 1.2 if self.currency < 5 else 1.5
        self.labor_capacity = 5  # Reset each cycle
        # Try to buy food, increase max price if failed last cycle
        max_price = 1.5
        if hasattr(self, 'failed_food_cycles'):
            self.failed_food_cycles += 1
            max_price += 0.5 * self.failed_food_cycles
        else:
            self.failed_food_cycles = 0
        if self.goods.get('food', 0) < 1 and self.currency >= max_price:
            economy_state.requests.append(Request(buyer_id=self.agent_id, good_name='food', quantity=1, max_price=max_price))
            economy_state.log_agent_decision(self.agent_id, f"Created buy request: 1 food @ max {max_price}.")



class Trader:
    def decide(self, economy_state):
        # Try to buy food if low
        if self.goods.get('food', 0) < 1 and self.currency >= 1.5:
            economy_state.requests.append(Request(buyer_id=self.agent_id, good_name='food', quantity=1, max_price=1.5))
            economy_state.log_agent_decision(self.agent_id, f"Created buy request: 1 food @ max 1.5.")
