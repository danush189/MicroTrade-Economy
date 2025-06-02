from agents import *
from crewai import Task

# Modular task definitions for the micro trade economy

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
