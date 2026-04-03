Paper Trading Simulator (Django)
Overview

This project is a Paper Trading Web Application built with Python and Django that allows users to simulate trading financial instruments (stocks) using real market data.

The purpose of this application is to demonstrate full-stack development skills, including:

 - Backend development with Django
 - Frontend UI design with HTML/CSS
 - Integration with external financial data APIs
 - Portfolio tracking and transaction management

This project was developed as a final portfolio submission for a coding bootcamp, fulfilling the requirement to build a functional, robust, and well-documented application .

   Project Objectives

This application satisfies the core requirements defined by the bootcamp:

 - Provide an initial cash balance for trading
 - Allow users to buy and sell financial instruments
 - Display current market prices and historical data
 - Maintain a transaction history
 - Track portfolio value over time
 - Allow resetting the account to default state
 - Implement using Python (Django framework)

**Features**

User Authentication
 - User registration (signup)
 - Login / Logout functionality
 - Session-based user state

📊 Market Data & Charting

 - Search for stock symbols (e.g., AAPL, TSLA)
 - Fetch real-time price data using Yahoo Finance (yfinance)
 - Display historical price chart using Chart.js
 - Show latest price and daily price change

💼 Trading Functionality
    - Buy stocks (only if sufficient cash is available)
    - Sell stocks (only if sufficient shares are owned)
    - Automatic calculation of transaction value
    - Input-based trading (user defines number of shares)

📁 Portfolio Management
    - Cash balance tracking
    - Holdings (positions):
    - hares owned
    - Purchase price
    - Current price
    - Profit / Loss
    - % Gain / Loss

Total portfolio value calculation (cash + holdings)

📜 Transaction History
Complete log of all trades:
    - Date
    - Symbol
    - Buy/Sell type
    - Shares
    - Price
    - Total value
    - Profit/Loss

📈 Performance Tracking
    - Portfolio value tracking over time
    - Daily snapshots of total portfolio value
    - Visual representation using charts

🔄 Reset Account
Reset account to initial state
    - Clears:
    - Trade history
    - Holdings
    - Portfolio data
    - Restores default starting cash balance

🖥️ Application Layout
The application is structured into multiple views/pages:
    Chart / Dashboard
        - Stock search
        - Price chart
        - Buy/Sell interface (if logged in)
    Portfolio
        - Cash balance
        - Total value
        - Portfolio performance chart
    Trade History
        - Table of All transactions
    Reset
        - Reset confirmation and execution
    Authentication
        - Login page
        - Signup page

🧱 Tech Stack
    Backend
        - Python
        - Django
    Frontend
        - HTML5
        - CSS3
        - JavaScript
    Libraries / APIs
        - yfinance → Market data retrieval
        - Chart.js → Data visualization

Installation & Setup
1. Clone the Project
    git clone https://github.com/yourusername/paper_trader.git
    cd paper_trader

2. Create Virtual Environment
    python -m venv venv

    Activate it:

     - Windows
        venv\Scripts\activate

     - Mac/Linux
        source venv/bin/activate

3. Install Dependencies
    pip install -r requirements.txt
    The project uses a minimal set of dependencies focused on Django, market data retrieval (yfinance), and data processing (pandas, numpy).

4. Apply Database Migrations
    python manage.py migrate

5. Run the Application
    python manage.py runserver

6. Access the Application
    Open your browser and go to: http://127.0.0.1:8000/

**How the Application Works**
Market Data
 - User enters a stock symbol
 - Backend retrieves data via yfinance
 - Data is displayed as a chart using Chart.js

Trading Logic
 - Buy:
    Validates available cash
    Updates holdings and cash balance

 - Sell:
    Validates owned shares
    Updates holdings and cash balance

 - Portfolio Calculation
    Total Value = Cash + Market Value of Holdings
    Profit/Loss calculated per position

 - Performance Tracking
    Daily portfolio value snapshots stored
    Used to generate performance charts

**Manual Testing Checklist**

The following scenarios were tested:

Authentication
    User can sign up
    User can log in and log out
    Invalid login is handled correctly

Market Data
    Valid ticker displays chart and price
    Invalid ticker does not crash application

Trading
    Buy succeeds with sufficient funds
    Buy fails when funds are insufficient
    Sell succeeds when shares are available
    Sell fails when attempting to sell more than owned

Portfolio
    Holdings update correctly after trades
    Cash balance updates correctly
    Profit/Loss calculations are accurate

History
    All transactions are recorded correctly

Reset
    Reset clears all data
    Account returns to default state

**Assumptions & Limitations**
--
    ✔ This is a simulation only (no real financial transactions)
    ✔ Uses latest available market price (not real-time execution engine)
    ✔ No advanced order types (limit orders, stop-loss, etc.)
    ✔ Portfolio performance is based on daily snapshots, not continuous tracking
    ✔ Designed for educational purposes

**Evaluation Criteria Alignment**

This project was developed to meet the bootcamp grading criteria:
--
    ✔ Functionality: Core trading and portfolio features implemented
    ✔ Robustness: Input validation and error handling included
    ✔ Creativity: Custom UI and dashboard layout
    ✔ Code Quality: Modular structure using Django apps and services
    ✔ GitHub Structure: Organized project layout
    ✔ Documentation: Installation and usage instructions provided

**Future Improvements**

If extended further, the application could include:
--
   ✔ Real-time price streaming (WebSockets)
   ✔ Candlestick charts
   ✔ Multiple portfolios per user
   ✔ Risk metrics (Sharpe ratio, volatility)
   ✔ REST API + React frontend
   ✔ Database upgrade to PostgreSQL

**Author**
Name: Rainier Rocafort
Description: Developed as part of a coding bootcamp portfolio project.

**License**

This project is intended for educational use only.
