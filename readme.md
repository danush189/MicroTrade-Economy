# Micro Trading Economy Simulation

A sophisticated multi-agent economic simulation built with CrewAI that models a small-scale trading economy with autonomous agents representing different economic roles.

## 🌟 Overview

This simulation creates a micro-economy where AI agents act as producers, consumers, traders, workers, and market facilitators. Each agent has specific goals, capabilities, and decision-making processes that drive realistic economic interactions including production, consumption, trading, labor markets, and price discovery.

## 🏗️ Architecture

### Core Components

- **Economy State Management**: Centralized state tracking for all agents, goods, transactions, and market conditions
- **Agent-Based Modeling**: Five distinct agent types with unique behaviors and objectives
- **Market Mechanics**: Dynamic pricing, offer/request matching, and transaction facilitation
- **Labor Market**: Worker agents can offer labor services to boost production
- **Health System**: Agents must consume resources to maintain health and survival

### Agent Types

| Agent | Role | Primary Goal | Key Capabilities |
|-------|------|--------------|------------------|
| **Producer** | Food Producer | Maximize profit through production and sales | Produce food, create sell offers, hire labor |
| **Consumer** | Food Consumer | Maintain health through food consumption | Buy food, create buy requests, survive |
| **Market** | Trade Facilitator | Facilitate trades and collect fees | Match offers/requests, earn transaction fees |
| **Worker** | Labor Provider | Earn currency through labor services | Offer labor, consume food, survive |
| **Trader** | Goods Trader | Profit through arbitrage | Buy low, sell high, market analysis |

## 🚀 Features

### Economic Mechanics
- **Dynamic Market Pricing**: Prices adjust based on supply and demand
- **Transaction Matching**: Automated matching of buy/sell orders
- **Labor Market**: Hire workers to boost production capacity
- **Currency System**: Track wealth and enable complex transactions
- **Health & Survival**: Agents must consume resources or face penalties

### Simulation Features
- **Multi-Cycle Simulation**: Run extended economic periods
- **State Persistence**: Save and resume simulations
- **Detailed Logging**: Track all transactions and agent decisions
- **Market Analysis**: View current offers, requests, and price trends

### AI Agent Capabilities
- **Autonomous Decision Making**: Each agent makes independent choices
- **Market Analysis**: Agents analyze conditions before acting
- **Strategic Planning**: Long-term goal optimization
- **Risk Management**: Balance survival needs with profit motives

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- OpenAI API key

### Setup

1. **Clone or download the project files**
   ```bash
   # Ensure you have micro_trade_economy.py in your project directory
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   
   Create a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

4. **Verify Installation**
   ```bash
   python micro_trade_economy.py
   ```

## 🎮 Usage

### Basic Simulation

Run a standard 5-cycle simulation:
```python
from micro_trade_economy import run_simulation

# Run 5 cycles with default settings
results = run_simulation(cycles=5)
```

### Advanced Usage

```python
from micro_trade_economy import run_simulation, ECONOMY

# Run simulation with custom parameters
results = run_simulation(
    cycles=10, 
    save_file="my_economy.json", 
    resume=False
)

# Resume from saved state
results = run_simulation(
    cycles=5, 
    save_file="my_economy.json", 
    resume=True
)

# Access economy state
print(f"Current cycle: {ECONOMY.cycle}")
print(f"Total transactions: {len(ECONOMY.transactions)}")
```

### Command Line Execution

```bash
# Run default simulation
python micro_trade_economy.py

# For extended simulations, modify the script's main section
```

## 📊 Understanding the Output

### Agent Status Reports
Each cycle provides detailed status for every agent:
```
producer: Health=100, Currency=15.5, Goods={'food': 3}
consumer: Health=95, Currency=5.2, Goods={'food': 1}
market: Health=100, Currency=2.1, Goods={}
worker: Health=90, Currency=8.7, Goods={'food': 2}
trader: Health=85, Currency=12.3, Goods={'food': 4}
```

### Market Activity
- **Offers**: Current sell orders with prices and quantities
- **Requests**: Current buy orders with maximum prices
- **Transactions**: Completed trades with details
- **Market Prices**: Current market rates for goods

### Economic Indicators
- **Price Trends**: Track inflation/deflation over time
- **Trade Volume**: Monitor market activity levels
- **Agent Wealth**: Observe wealth distribution changes
- **Health Metrics**: Track agent survival and wellbeing

## 🔧 Configuration

### Customizing Agent Behavior

Modify agent prompts in the task descriptions to change behavior:
```python
producer_task = Task(
    description="""
    Your custom behavior description here...
    """,
    agent=producer_agent,
    expected_output="Expected output format"
)
```

### Economic Parameters

Adjust economic settings by modifying initialization:
```python
def initialize_economy():
    # Modify starting conditions
    producer_state.goods["food"] = 10  # More initial food
    consumer_state.currency = 20       # More starting currency
    ECONOMY.update_market_price("food", 1.5)  # Different starting price
```

### Adding New Goods

Extend the economy with additional tradeable goods:
```python
# Add new production tools
@tool("Produce Tools")
def produce_tools_tool(agent_id: str) -> str:
    return ProduceTool("tools").run(agent_id)

# Update agent inventories and market prices
ECONOMY.update_market_price("tools", 5.0)
```

## 📈 Analysis and Monitoring

### Key Metrics to Track

1. **Economic Health**
   - Total currency in circulation
   - Price stability over time
   - Transaction volume trends

2. **Agent Performance**
   - Individual agent wealth accumulation
   - Health maintenance success rates
   - Trading strategy effectiveness

3. **Market Efficiency**
   - Price discovery speed
   - Supply/demand balance
   - Market maker profits

### Data Export

The simulation saves detailed state information:
```python
# Access transaction history
for tx in ECONOMY.transactions:
    print(f"Transaction: {tx.seller_id} -> {tx.buyer_id}, "
          f"{tx.quantity} {tx.good_name} @ {tx.price}")

# Export to custom format
import json
with open('analysis_data.json', 'w') as f:
    json.dump(ECONOMY.model_dump(), f, indent=2)
```

## 🔬 Research Applications

### Economic Research
- **Market Dynamics**: Study price formation and market efficiency
- **Agent Behavior**: Analyze decision-making under scarcity
- **System Resilience**: Test economy response to shocks

### AI Research
- **Multi-Agent Systems**: Explore emergent behaviors
- **Game Theory**: Analyze strategic interactions
- **Machine Learning**: Study adaptation and learning

### Educational Use
- **Economics Teaching**: Demonstrate market principles
- **Simulation Design**: Learn agent-based modeling
- **AI Ethics**: Explore fairness in automated systems

## 🛡️ Troubleshooting

### Common Issues

**OpenAI API Key Error**
```
AssertionError: OPENAI_API_KEY not found in environment!
```
- Ensure `.env` file exists with valid API key
- Check environment variable is properly set

**Agent Tool Execution Errors**
```
Error: Agent producer not found
```
- Verify agent initialization ran successfully
- Check agent_id parameters match exactly

**Simulation Hangs or Crashes**
```
Agent decision making timeout
```
- Reduce simulation complexity
- Check API rate limits
- Verify agent prompts are clear and actionable

### Performance Optimization

- **Reduce API Calls**: Simplify agent decision prompts
- **Batch Operations**: Group similar operations together
- **State Management**: Clear old data between cycles
- **Logging Level**: Adjust logging verbosity for performance

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Areas for Contribution
- Additional agent types (banker, manufacturer, etc.)
- More sophisticated economic models
- Visualization and analysis tools
- Performance optimizations
- Educational materials and examples

## 📝 License

This project is open source. Feel free to modify and extend for your research, educational, or commercial needs.

## 🙏 Acknowledgments

- Built with [CrewAI](https://github.com/joaomdmoura/crewAI) framework
- Powered by OpenAI's language models
- Inspired by agent-based economic modeling research

## 📞 Support

For questions, issues, or contributions:
- Check the troubleshooting section above
- Review the code comments for implementation details
- Consider the educational and research applications for your use case

---

**Happy Simulating!** 🎯📊🤖