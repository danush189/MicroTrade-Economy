import os
import logging
from dotenv import load_dotenv
import tools
from models import EconomyState
from tools import *
from agents import *
from tasks import *
from crewai import Crew, Process

# Setup action logger for agent activities
logger = logging.getLogger("agent_actions")
logger.setLevel(logging.INFO)
logger.handlers = []  # Clear any existing handlers

# Create file handler
file_handler = logging.FileHandler('actions.log', mode='w')
file_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(file_handler)

# Load environment variable
load_dotenv()

# Verify OpenAI API key is available
assert os.getenv("OPENAI_API_KEY"), "OpenAI API key not found! Please add it to your .env file"

# Global state to be shared by all agents
ECONOMY = EconomyState()
tools.ECONOMY = ECONOMY

def initialize_economy():
    """Initialize the economy with balanced starting conditions"""    # Create agent states
    ECONOMY.add_agent("producer")
    ECONOMY.add_agent("market")
    ECONOMY.add_agent("worker")
    ECONOMY.add_agent("trader")
    ECONOMY.add_agent("worker")
    ECONOMY.add_agent("trader")

    # Initialize producer with resources to kickstart production
    producer_state = ECONOMY.get_agent_state("producer")
    producer_state.goods["food"] = 8  # More initial food to sell
    producer_state.currency = 15.0  # Extra capital to hire labor

    worker_state = ECONOMY.get_agent_state("worker")
    worker_state.goods["food"] = 2
    worker_state.currency = 12.0  # Enough to survive while establishing labor contracts

    trader_state = ECONOMY.get_agent_state("trader")
    trader_state.goods["food"] = 2
    trader_state.currency = 15.0  # Capital for trading operations

    market_state = ECONOMY.get_agent_state("market")
    market_state.currency = 20.0  # Increased initial market currency for liquidity

    # Initialize market prices - start lower to encourage early trading
    ECONOMY.update_market_price("food", 1.5)  # Lower initial food price
    return "Economy initialized with balanced starting conditions."

def end_cycle():
    """End the current cycle and prepare for the next one"""
    cycle_num = ECONOMY.cycle
    ECONOMY.cycle += 1

    # Reset labor capacity
    ResetLaborTool().run(agent_id="market")
    logger.info(f"\n===== End of Cycle {cycle_num} =====")

    # Natural health recovery first
    ECONOMY.natural_health_recovery()

    # Process food consumption and health changes
    consumption_status = {agent_id: False for agent_id in ECONOMY.agents if agent_id != "market"}

    # Check transactions for food consumption
    for tx in ECONOMY.transactions:
        if tx.good_name == "food" and tx.buyer_id in consumption_status:
            consumption_status[tx.buyer_id] = True

    # Process each agent's food consumption and health
    for agent_id, consumed in consumption_status.items():
        agent_state = ECONOMY.get_agent_state(agent_id)

        # Try to consume from inventory if not already consumed
        if not consumed and "food" in agent_state.goods and agent_state.goods["food"] > 0:
            food_price = ECONOMY.market_prices.get("food", 1.0)
            if agent_state.currency >= food_price:
                agent_state.goods["food"] -= 1
                agent_state.currency -= food_price
                ECONOMY.log_agent_decision(agent_id, f"Consumed 1 food from inventory for {food_price} currency")
                consumed = True
            else:
                # Emergency food assistance
                ECONOMY.provide_food_subsidy()

        # Update health based on consumption with reduced penalties
        if consumed:
            agent_state.health = min(100, agent_state.health + 5)
            ECONOMY.log_agent_decision(agent_id, f"Maintained health at {agent_state.health}")
        else:
            agent_state.health = max(0, agent_state.health - 8)  # Reduced penalty
            ECONOMY.log_agent_decision(agent_id, f"Health decreased to {agent_state.health} (no food consumed)")

    # Dynamic pricing based on supply and demand with price controls
    total_food = sum(agent.goods.get("food", 0) for agent in ECONOMY.agents.values())
    new_price = max(ECONOMY.min_food_price, min(ECONOMY.max_food_price, 10 / (total_food + 1)))
    ECONOMY.update_market_price("food", new_price)

    # Redistribution mechanism
    ECONOMY.redistribute_tax_pool()

    # Labor utilization and incentives
    for offer in ECONOMY.offers:
        if offer.good_name == "labor" and offer.price <= 2.0:  # Incentivize affordable labor
            producer_state = ECONOMY.get_agent_state("producer")
            if producer_state and producer_state.currency >= offer.price:
                producer_state.currency -= offer.price
                worker_state = ECONOMY.get_agent_state(offer.seller_id)
                if worker_state:
                    worker_state.currency += offer.price
                    producer_state.labor_used += offer.quantity
                    ECONOMY.log_agent_decision("producer", f"Hired {offer.quantity} labor units for {offer.price} currency")
                    ECONOMY.log_agent_decision(offer.seller_id, f"Labor contract fulfilled for {offer.price} currency")

    # Emergency intervention for critical situations
    for agent_id, agent_state in ECONOMY.agents.items():
        if agent_id != "market" and agent_state.health < 30:
            ECONOMY.provide_food_subsidy()

    # Clear cycle state
    ECONOMY.offers = []
    ECONOMY.requests = []
    ECONOMY.transactions = []

    # Finalize logs
    ECONOMY.finalize_cycle_logs()
    ECONOMY.save_logs_to_file()

    cycle_message = f"Ended cycle {cycle_num}. Starting cycle {ECONOMY.cycle}"
    logger.info(f"\n{cycle_message}")
    return cycle_message

def run_simulation(cycles=5, save_file: str = "economy_state.json", resume: bool = False):
    """Run the economic simulation for the specified number of cycles"""
    global ECONOMY
    
    # Initialize or load economy state
    if resume and os.path.exists(save_file):
        ECONOMY = EconomyState.load(save_file)
        logger.info(f"Resumed simulation from {save_file}")
    else:
        initialize_economy()
        logger.info("Initialized new economy simulation")
      # Set up the crew of agents
    economy_crew = Crew(
        agents=[producer_agent, market_agent, worker_agent, trader_agent],
        tasks=[producer_task, market_task, worker_task, trader_task],
        verbose=True,
        process=Process.sequential,
    )
    
    # Run simulation cycles
    results = []
    for cycle in range(cycles):
        logger.info(f"\n===== Starting Cycle {cycle + 1} =====")
        
        # Run agent tasks
        cycle_results = economy_crew.kickoff()
        results.append(cycle_results)
        
        # Process cycle end
        end_cycle()
        
        # Log cycle summary
        logger.info("\n===== Cycle Summary =====")
        for agent_id, state in sorted(ECONOMY.agents.items()):
            logger.info(f"{agent_id}: Health={state.health}, Currency={state.currency:.1f}, Goods={state.goods}")
    
    # Save final state
    ECONOMY.save(save_file)
    logger.info(f"\nSimulation completed. State saved to {save_file}")
    return results

if __name__ == "__main__":
    run_simulation(3)
