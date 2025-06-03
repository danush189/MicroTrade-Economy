from agents import *
from crewai import Task

# Modular task definitions for the micro trade economy

producer_task = Task(
    description="""
    As a food producer, your job is to:
    
    1. Check your inventory and health: 
       - Use: Check Inventory (agent_id="producer")
       - Monitor your health - if below 70, prioritize using labor
    
    2. Check market for labor:
       - Use: View Market (agent_id="producer")
       - IMPORTANT: Hire labor when available at ≤2.0 currency per unit
       - Producing without labor costs 5 health points!
       - Use: Hire Labor (agent_id="producer", offer_id="offer_XXXX")
    
    3. Produce food strategically: 
       - Use: Produce Food (agent_id="producer", use_labor=True)  # Set use_labor=True when you have hired labor
       - Using labor increases production and prevents health loss
       - Without labor, you'll lose 5 health points per production
    
    4. Consume food to maintain your health: 
       - Use: Consume Food (agent_id="producer", good_name="food", quantity=1)
       - ALWAYS do this each cycle or your health will decrease
    
    5. Create offers to sell surplus food:
       - Use: Create Sell Offer (agent_id="producer", good_name="food", quantity=X, price=Y)
       - Keep 2-3 units in reserve (more if health is low)
       - Price based on production method: with labor (1.5-2.0), without labor (2.0-2.5)
    
    IMPORTANT PRIORITIES: 
    1. Maintain health above 70
    2. Use labor whenever possible
    3. Keep sufficient food reserves
    4. Sell surplus at fair prices
    
    Strategy Tips:
    - If health < 70: Focus on using labor and building reserves
    - If health > 70: Can produce without labor if needed
    - Price food higher when produced without labor (covers health cost)
    - Always check for labor offers before producing
    - Build emergency fund of 10-15 currency for labor hiring
    """,
    agent=producer_agent,
    expected_output="A summary of actions taken and current status",
)

market_task= Task(
    description="""
    As a market facilitator, your job is to:
    1. Monitor market health:
       - Use: View Market (agent_id="market")
       - Track price trends and supply/demand
       - Identify agents in financial distress
    
    2. Price Stabilization:
       - Keep food prices between 1.0 and 2.5 currency
       - Encourage trade during price extremes:
         * When prices > 2.0: Prioritize matching low-price sellers
         * When prices < 1.2: Prioritize higher-price sellers
    
    3. Match trades strategically:
       - Use: Match Market (agent_id="market")
       - Prioritize matching order:
         1. Emergency needs (agents with health < 50)
         2. Basic needs (agents with no food)
         3. Standard trades (regular supply/demand)
    
    4. Monitor system health:
       - Use: Check Inventory (agent_id="market")
       - Track fees collected
       - Monitor overall economic activity
    
    MARKET INTERVENTION GUIDELINES:
    - When food prices > 2.0:
      * Encourage producers to use labor (increases supply)
      * Prioritize matches for agents with low health
    
    - When multiple agents have low health:
      * Facilitate emergency food distribution
      * Enable price discounts for struggling agents
    
    - When labor market is stagnant:
      * Encourage producer-worker matches
      * Facilitate fair labor pricing
    
    IMPORTANT:
    - Your role is to maintain market stability
    - Prevent extreme price fluctuations
    - Ensure basic needs are met
    - Balance profit with social welfare
    
    Success Metrics:
    1. Stable food prices (1.0-2.5 range)
    2. High trade volume
    3. Few agents in critical health
    4. Active labor market
    """,
    agent=market_agent,
    expected_output="A detailed summary of market activity, trades facilitated, and fees collected",
)

worker_task = Task(
    description="""
    As a labor provider, your job is to:
    1. Check your status and inventory:
       - Use: Check Inventory (agent_id="worker")
       - Monitor your health and currency closely
    
    2. View market conditions:
       - Use: View Market (agent_id="worker")
       - Check food prices and existing labor offers
       - Analyze producer's activity
    
    3. Adjust labor pricing strategy:
       PRICING GUIDELINES:
       - If health > 80 and currency > 15: Price at 1.8-2.0
       - If health 50-80 or currency 10-15: Price at 1.5-1.8
       - If health < 50 or currency < 10: Price at 1.2-1.5
       - Never price below 1.0 (minimum living wage)
    
    4. Offer your labor services:
       - Use: Offer Labor (agent_id="worker", target_agent_id="producer", labor_units=X, price_per_unit=Y)
       - Offer smaller quantities (2-3 units) when prices are high
       - Offer larger quantities (4-5 units) when prices are low
    
    5. Consume food to maintain health:
       - Use: Consume Food (agent_id="worker", good_name="food", quantity=1)
       - CRITICAL: Do this EVERY cycle
       - Try to maintain 2 food units in reserve
    
    6. Manage food supply:
       - Create Buy Request when food < 2 units
       - Accept any food offers at or below current market price
       - Reserve enough currency for 2 cycles of food
    
    SURVIVAL STRATEGIES:
    If health < 50 or currency < 5:
    1. Lower labor prices immediately
    2. Offer smaller quantities to conserve energy
    3. Use any subsidies to buy food first
    4. Request emergency food assistance if available
    
    IMPORTANT REMINDERS:
    - Your health affects your earning potential
    - Balance between competitive pricing and survival
    - Build reserves during good times
    - Adapt prices to market conditions
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
