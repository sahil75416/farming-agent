# farming-agent

An AI farming agent that manages a farm over 30 days by optimizing crop and animal production, resource allocation, and market trading.

## Features

- **Crop Management**: Plants and harvests wheat, carrots, tomatoes, strawberries, and melons with strategic timing and watering schedules
- **Animal Husbandry**: Manages geese, cows, and sheep with feeding, care, and fertilizer collection
- **Worker Scheduling**: Coordinates multiple farm hands to prioritize tasks based on urgency and efficiency
- **Market Trading**: Buys and sells seeds, animals, products, and land based on profitability analysis
- **Dynamic Strategy**: Adapts tactics based on remaining days, resource prices, and opponent behavior
- **Feasibility Checking**: Validates all actions before execution to handle constraints

## Game Rules

- **Duration**: 30-day farming cycle
- **Workforce**: Farmer + hired hands (up to 13 total)
- **Map**: 10x10 grid with shed at (4,4)-(5,5), expandable to 4 quadrants
- **Resources**: Money, seeds, animals, fertilizer, and crop yields
- **Market**: Dynamic pricing for products and animals

## Core Algorithm

1. **State Analysis**: Scans the farm for plants, animals, weeds, and available tiles
2. **Job Generation**: Creates prioritized task list (planting, feeding, harvesting, building, etc.)
3. **Task Assignment**: Uses cost-based worker matching with urgency preemption for critical jobs
4. **Execution**: Moves workers to target tiles and executes actions
5. **Market Strategy**: Automatically buys/sells to maximize profit while maintaining production balance

## Key Metrics

- Opponent-aware animal caps to avoid mirroring strategies
- Wheat buffer system for consistent animal feeding
- Melon-specific planting window (days 1-16)
- Late-game shutdowns and end-of-day rush handling
- Fertilizer optimization for wheat crops
