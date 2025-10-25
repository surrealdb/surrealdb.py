# Jupyter Notebooks + SurrealDB Examples

Interactive Jupyter notebooks demonstrating SurrealDB integration, data analysis, visualization, and real-time queries. Perfect for data exploration, prototyping, and learning.

## Features

- **Interactive Learning**: Step-by-step tutorials with live code
- **CRUD Operations**: Complete examples with explanations
- **Data Analysis**: Pandas integration for data manipulation
- **Visualizations**: Beautiful charts with Matplotlib and Plotly
- **Live Queries**: Real-time data updates in notebooks
- **Sample Datasets**: Pre-loaded data for experimentation
- **Best Practices**: Production-ready patterns

## Prerequisites

- Python 3.10+
- Docker (for running SurrealDB)
- Jupyter Notebook or JupyterLab

## Installation

### Option 1: Using uv (Recommended - Fast!)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Copy environment file
cp .env.example .env

# Start SurrealDB
docker compose up -d
```

### Option 2: Using pip (Universal)

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Start SurrealDB
docker compose up -d
```

## Running Jupyter

### With uv (Recommended)

```bash
# Start Jupyter Notebook
uv run jupyter notebook

# Or Jupyter Lab
uv run jupyter lab
```

### With pip

```bash
# Start Jupyter Notebook
jupyter notebook

# Or Jupyter Lab
jupyter lab
```

Your browser will open automatically. Navigate to the `notebooks/` folder.

## Notebooks

### 1. Getting Started (`01_getting_started.ipynb`)
**Perfect for beginners**
- Installing and importing SurrealDB
- Connecting to the database
- Basic queries and operations
- Understanding the data model
- Schema exploration

### 2. CRUD Operations (`02_crud_operations.ipynb`)
**Learn the fundamentals**
- Creating records
- Reading and querying data
- Updating existing records
- Deleting data
- Batch operations
- Error handling

### 3. Queries & Filtering (`03_queries_filtering.ipynb`)
**Advanced querying**
- SurrealQL examples
- Filtering and WHERE clauses
- Joins and relationships
- Aggregations (COUNT, SUM, AVG)
- Sorting and pagination
- Complex queries

### 4. Data Analysis (`04_data_analysis.ipynb`)
**Data science workflows**
- Importing data to Pandas DataFrames
- Data transformations and cleaning
- Statistical analysis
- Time series analysis
- Grouping and aggregations
- Exporting results

### 5. Visualization (`05_visualization.ipynb`)
**Create beautiful charts**
- Line charts (trends over time)
- Bar charts (comparisons)
- Scatter plots (correlations)
- Pie charts (proportions)
- Heatmaps (patterns)
- Interactive dashboards with Plotly

### 6. Live Queries (`06_live_queries.ipynb`)
**Real-time data**
- Subscribing to database changes
- Handling live updates
- Real-time visualizations
- Event-driven workflows
- Async patterns in notebooks

## Quick Start

1. **Start SurrealDB**:
   ```bash
   docker compose up -d
   ```

2. **Launch Jupyter**:
   ```bash
   uv run jupyter notebook
   # or
   jupyter notebook
   ```

3. **Open a notebook**:
   - Navigate to `notebooks/`
   - Start with `01_getting_started.ipynb`
   - Run cells sequentially (Shift+Enter)

## Project Structure

```
jupyter/
├── README.md                          # This file
├── pyproject.toml                     # Modern dependencies (uv)
├── requirements.txt                   # Universal dependencies (pip)
├── .env.example                       # Environment template
├── docker-compose.yml                 # SurrealDB setup
├── config.py                          # Configuration helper
├── database.py                        # Connection helper
├── utils.py                           # Utility functions
└── notebooks/                         # Interactive notebooks
    ├── 01_getting_started.ipynb       # Basics
    ├── 02_crud_operations.ipynb       # CRUD
    ├── 03_queries_filtering.ipynb     # Queries
    ├── 04_data_analysis.ipynb         # Analysis
    ├── 05_visualization.ipynb         # Charts
    └── 06_live_queries.ipynb          # Real-time
```

## Configuration

Environment variables (`.env`):

```
SURREALDB_URL=ws://localhost:8000/rpc
SURREALDB_NAMESPACE=test
SURREALDB_DATABASE=test
SURREALDB_USERNAME=root
SURREALDB_PASSWORD=root
```

## Tips & Tricks

### Jupyter Shortcuts
- `Shift+Enter`: Run cell and move to next
- `Ctrl+Enter`: Run cell and stay
- `A`: Insert cell above
- `B`: Insert cell below
- `DD`: Delete cell
- `M`: Convert to markdown
- `Y`: Convert to code

### Database Helpers

The notebooks include helper functions:

```python
from database import get_connection
from utils import pretty_print, sample_data

# Get a database connection
db = await get_connection()

# Pretty print results
pretty_print(users)

# Load sample data
await sample_data(db)
```

### Auto-reload

For development, enable auto-reload:

```python
%load_ext autoreload
%autoreload 2
```

## Sample Datasets

The notebooks include sample datasets:
- **Users**: Realistic user profiles
- **Products**: E-commerce product catalog
- **Orders**: Transaction history
- **Time Series**: Sensor data

## Visualizations Gallery

The visualization notebook creates:
- 📈 **Line Charts**: Sales trends, user growth
- 📊 **Bar Charts**: Product comparisons, category analysis
- 🔵 **Scatter Plots**: Price vs rating, correlations
- 🥧 **Pie Charts**: Market share, distribution
- 🎨 **Heatmaps**: Activity patterns, correlations
- 📱 **Interactive Dashboards**: Plotly widgets

## Learn More

- [Jupyter Documentation](https://jupyter.org/documentation)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Matplotlib Gallery](https://matplotlib.org/stable/gallery/)
- [Plotly Examples](https://plotly.com/python/)
- [SurrealDB Python SDK](https://surrealdb.com/docs/sdk/python)

## Troubleshooting

### Kernel Dies
If the kernel dies when running cells:
```bash
# Restart Jupyter
# Check SurrealDB is running
docker compose ps
```

### Import Errors
```bash
# Reinstall dependencies
uv sync
# or
pip install -r requirements.txt
```

### Connection Issues
```bash
# Check .env file
cat .env

# Verify SurrealDB
curl http://localhost:8000/health
```

## Development

### Adding New Notebooks

1. Create new `.ipynb` file in `notebooks/`
2. Follow naming convention: `XX_description.ipynb`
3. Include markdown cells for documentation
4. Add to this README

### Exporting Notebooks

```bash
# Export to Python script
jupyter nbconvert --to python notebooks/01_getting_started.ipynb

# Export to HTML
jupyter nbconvert --to html notebooks/*.ipynb
```

## Use Cases

Perfect for:
- 📚 **Learning** SurrealDB interactively
- 🔬 **Prototyping** new features
- 📊 **Data Analysis** and reporting
- 📈 **Visualization** of database data
- 🎓 **Teaching** database concepts
- 🔍 **Exploration** of data patterns

