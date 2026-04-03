# Create your tests here.

from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal

from core.models import Portfolio, Holding
from core.trade_services import execute_trade


class TradeTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.portfolio = Portfolio.objects.create(user=self.user, cash_balance=Decimal("1000.00"))

    def test_buy_fails_with_insufficient_cash(self):
        """
        Attempt to buy shares that exceed available cash.
        Should fail and not modify portfolio.
        """
        result = execute_trade(
            user=self.user,
            symbol="AAPL",
            shares=Decimal("1000"),  # intentionally large
            trade_type="BUY"
        )

        self.assertFalse(result["ok"])

        # Ensure cash unchanged
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash_balance, Decimal("1000.00"))

    def test_sell_fails_with_insufficient_shares(self):
        """
        Attempt to sell shares that are not owned.
        Should fail and not modify portfolio.
        """
        result = execute_trade(
            user=self.user,
            symbol="AAPL",
            shares=Decimal("10"),
            trade_type="SELL"
        )

        self.assertFalse(result["ok"])

    def test_successful_buy_reduces_cash(self):
        """
        Successful buy should reduce cash and create holding.
        """
        result = execute_trade(
            user=self.user,
            symbol="AAPL",
            shares=Decimal("1"),
            trade_type="BUY"
        )

        self.assertTrue(result["ok"])

        self.portfolio.refresh_from_db()
        self.assertLess(self.portfolio.cash_balance, Decimal("1000.00"))

        holding = Holding.objects.filter(portfolio=self.portfolio, symbol="AAPL").first()
        self.assertIsNotNone(holding)
