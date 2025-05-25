import os
import sys
import time
from typing import Dict, Any, List

# Add the parent directory to the path so we can import the simulation module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from micro_trade_economy import (
    run_simulation, 
    ECONOMY, 
    Good, 
    initialize_economy, 
    producer_agent,
    consumer_agent,
    market_agent,
    worker_agent,
    trader_agent,
    ProduceTool
)

def display_welcome():
    """Display a welcome message and explanation of the simulation"""
    print("""
    ╔════════════════════════════════════════════╗
    ║             MICROTRADE ECONOMY             ║
    ║            SIMULATION TUTORIAL             ║
    ╚════════════════════════════════════════════╝
    
    This tutorial will guide you through running and
    modifying the MicroTrade Economy simulation.
    
    The simulation models a basic economy with:
    - Producers who create goods
    - Consumers who need goods to survive
    - Workers who offer labor
    - Traders who buy low and sell high
    - A Market that facilitates exchanges
    
    Let's begin!
    """)

def basic_simulation():
    """Run a basic simulation"""
    print("\n1. RUNNING BASIC SIMULATION (3 CYCLES)")
    print("=====================================")
    print("This will run the simulation for 3 cycles with default settings.")
    time.sleep(1)
    
    results = run_simulation(3)
    
    print("\nBASIC SIMULATION COMPLETE!")
    return results

def modified_simulation():
    """Run a simulation with modified parameters"""
    print("\n2. RUNNING MODIFIED SIMULATION (5 CYCLES)")
    print("=======================================")
    print("This will run the simulation with modified parameters:")
    print("- Producer starts with more food (10 units)")
    print("- Market fees increased to 10%")
    print("- Consumer has more starting currency (20)")
    time.sleep(1)
    
    # Reset and initialize the economy with custom settings
    initialize_economy()
    
    # Modify producer's starting inventory
    producer_state = ECONOMY.get_agent_state("producer")
    producer_state.goods["food"] = 10
    
    # Modify consumer's starting currency
    consumer_state = ECONOMY.get_agent_state("consumer")
    consumer_state.currency = 20.0
    
    # Run the simulation
    results = run_simulation(5)
    
    print("\nMODIFIED SIMULATION COMPLETE!")
    return results

def analyze_results(basic_results, modified_results):
    """Analyze and compare results from different simulations"""
    print("\n3. ANALYZING SIMULATION RESULTS")
    print("=============================")
    
    # Extract final states
    basic_final_states = {agent_id: state for agent_id, state in ECONOMY.agents.items()}
    
    print("\nComparison of final states:")
    print("---------------------------")
    
    for agent_id, state in basic_final_states.items():
        print(f"{agent_id.capitalize()}:")
        print(f"  Health: {state.health}")
        print(f"  Currency: {state.currency}")
        print(f"  Goods: {state.goods}")
    
    # Calculate overall economy statistics
    total_currency = sum(state.currency for state in basic_final_states.values())
    total_goods = sum(sum(goods.values()) for goods in 
                      [state.goods for state in basic_final_states.values() if state.goods])
    
    print("\nOverall Economy Statistics:")
    print("--------------------------")
    print(f"Total Currency in Economy: {total_currency}")
    print(f"Total Goods in Economy: {total_goods}")
    
    if 'food' in ECONOMY.market_prices:
        print(f"Final Market Price for Food: {ECONOMY.market_prices['food']}")

def show_custom_configuration_options():
    """Display options for customizing the simulation"""
    print("\n4. CUSTOMIZATION OPTIONS")
    print("======================")
    print("Here are ways you can customize the simulation:")
    
    print("\nA. Adding New Goods")
    print("-----------------")
    print("""
    # Add a new good type to the economy
    ECONOMY.update_market_price("tools", 5.0)
    
    # Create a new production tool for the new good
    tools_production_tool = ProduceTool("tools", production_rate=1)
    
    # Add the new tool to the producer agent
    producer_agent.tools.append(tools_production_tool.run)
    """)
    
    print("\nB. Adjusting Agent Behavior")
    print("-------------------------")
    print("""
    # Make the trader more aggressive in pricing
    trader_agent.backstory = "You are an aggressive trader who takes more risks for higher returns."
    
    # Give the consumer more starting resources
    consumer_state = ECONOMY.get_agent_state("consumer")
    consumer_state.currency = 30.0
    """)
    
    print("\nC. Creating New Agent Types")
    print("-------------------------")
    print("""
    # Create a specialized producer agent
    from crewai import Agent
    
    specialized_producer = Agent(
        role="Advanced Producer",
        goal="Produce high-value specialized goods",
        backstory="You create advanced tools that greatly enhance productivity.",
        verbose=True,
        allow_delegation=False,
        tools=[
            ProduceTool("advanced_tools", production_rate=1).run,
            CreateOfferTool().run,
            CheckInventoryTool().run,
            ViewMarketTool().run,
        ]
    )
    
    # Add the new agent to the economy
    ECONOMY.add_agent("specialized_producer")
    """)

def main():
    """Main function to run the tutorial"""
    display_welcome()
    input("Press Enter to start the basic simulation...")
    
    basic_results = basic_simulation()
    input("\nPress Enter to run the modified simulation...")
    
    modified_results = modified_simulation()
    input("\nPress Enter to see the analysis...")
    
    analyze_results(basic_results, modified_results)
    input("\nPress Enter to see customization options...")
    
    show_custom_configuration_options()
    
    print("\n\nTUTORIAL COMPLETE!")
    print("Thank you for exploring the MicroTrade Economy simulation.")
    print("You can now modify and extend the simulation to build more complex economic models.")

if __name__ == "__main__":
    main()
